from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractError, GovernedAuthorityContractCatalog
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    ReferenceDataset,
)
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _setup() -> tuple[GameplayEventStore, str, str]:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(
        store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)
    )
    branch_ref = "branch:government:promotion"
    candidate = BatchIntentCandidate(
        intent_ref="intent:branch:government:promotion",
        profile_ref="character:char_a",
        intent_kind="inspection",
        payload={
            "organization_ref": "organization:bakery",
            "inspection_ref": "inspection:branch:promotion",
            "jurisdiction_ref": "jurisdiction:bakery",
            "policy_digest": "sha256:policy:promotion",
            "evidence_ref": "evidence:branch:promotion",
            "passed": True,
        },
        priority=1,
        policy_revision="policy:promotion",
        package_revision="package:promotion",
        idempotency_key="intent:branch:government:promotion",
        correlation_id="corr:branch:government:promotion",
        source_ref="planner",
        privacy_scope="actor:self",
        expected_revisions={"gameplay:government:organization:bakery": 0},
    )
    accepted = authority.preview(
        request=BranchPreviewRequest(
            branch_ref=branch_ref,
            world_ref="world:bakery",
            base_event_digest="sha256:empty",
            deterministic_seed="seed:promotion",
            active_revision_refs=("mode:promotion",),
            calibration_ref="calibration:promotion",
            privacy_scope="creator_debug",
        ),
        dataset=ReferenceDataset(
            dataset_ref="dataset:promotion",
            provenance="fixture",
            license_ref="license:permitted",
            schema_revision="1",
            digest="sha256:dataset:promotion",
            classification="creator_debug",
            allowed_scopes=("creator_debug",),
        ),
        calibration=CalibrationInput(
            calibration_ref="calibration:promotion",
            dataset_ref="dataset:promotion",
            parameter_mapping_revision="map:promotion",
            world_revision="world:promotion",
            ruleset_revision="rules:promotion",
            privacy_scope="creator_debug",
        ),
        family_inputs=(),
        candidates=(candidate,),
        mode=WorldModeProfile(
            world_ref="world:bakery",
            mode="preview",
            revision="mode:promotion",
            cadence_class="daily",
            batch_limit=1,
            wake_budget=1,
            catch_up_limit=1,
            allowed_intent_kinds=("inspection",),
            degraded_threshold=1,
        ),
    )
    assert accepted.accepted
    scenario_receipt = authority.settle_accepted_inspection_scenario(
        branch_ref=branch_ref, intent_ref=candidate.intent_ref
    )
    assert scenario_receipt.committed
    admission_stream = authority.admission_stream_id(branch_ref=branch_ref)
    scenario_stream = GovernmentAuthority.branch_scenario_stream_id(
        branch_ref=branch_ref, organization_ref="organization:bakery"
    )
    admission_event_id = store.read_stream(admission_stream)[0].event_id
    scenario_event_id = store.read_stream(scenario_stream)[0].event_id
    return store, admission_event_id, scenario_event_id


def test_government_promotes_one_durable_passed_inspection_into_existing_production_stream() -> None:
    store, admission_event_id, scenario_event_id = _setup()

    result = GovernmentAuthority(store=store).promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:1",
        privacy_scope="project",
    )

    assert result.accepted
    assert result.receipt is not None
    assert store.get_stream_head("gameplay:government:organization:bakery") == 1
    event = store.read_stream("gameplay:government:organization:bakery")[0]
    assert event.event_type == "gameplay.government.inspection_recorded"
    assert event.visibility_policy == "project"
    assert event.payload["branch_ref"] == "branch:government:promotion"
    assert event.payload["branch_admission_event_id"] == admission_event_id
    assert event.payload["branch_scenario_event_id"] == scenario_event_id


def test_government_promotion_exact_duplicate_reconstructs_receipt_without_second_append() -> None:
    store, admission_event_id, scenario_event_id = _setup()
    government = GovernmentAuthority(store=store)

    first = government.promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:duplicate",
        privacy_scope="project",
    )
    duplicate = government.promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:duplicate",
        privacy_scope="project",
    )

    assert first.accepted and duplicate.accepted
    assert first.receipt is not None and duplicate.receipt is not None
    assert duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
    assert store.get_stream_head("gameplay:government:organization:bakery") == 1


def test_government_promotion_rejects_changed_duplicate_without_append() -> None:
    store, admission_event_id, scenario_event_id = _setup()
    government = GovernmentAuthority(store=store)
    assert government.promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:changed",
        privacy_scope="project",
    ).accepted

    rejected = government.promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:government:inspection:changed",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "idempotency_key_reused"
    assert store.get_stream_head("gameplay:government:organization:bakery") == 1


def test_government_promotion_rejects_stale_production_source_without_append() -> None:
    store, admission_event_id, scenario_event_id = _setup()
    government = GovernmentAuthority(store=store)
    assert government.settle_tax_assessment(
        organization_ref="organization:bakery",
        period_ref="period:promotion-source-advance",
        revenue=10.0,
        rate=0.1,
        policy_revision="policy:promotion-source-advance",
        command_id="command:promotion-source-advance",
        idempotency_key="idempotency:promotion-source-advance",
        causation_id="cause:promotion-source-advance",
        correlation_id="corr:promotion-source-advance",
    ).committed

    rejected = government.promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:stale",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_revision_conflict"
    assert store.get_stream_head("gameplay:government:organization:bakery") == 1


def test_government_promotion_rejects_wrong_privacy_without_append() -> None:
    store, admission_event_id, scenario_event_id = _setup()

    rejected = GovernmentAuthority(store=store).promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:privacy",
        privacy_scope="creator_debug",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_privacy_denied"
    assert store.get_stream_head("gameplay:government:organization:bakery") == 0


def test_government_promotion_rejects_forged_scenario_identity_without_append() -> None:
    store, admission_event_id, _ = _setup()

    rejected = GovernmentAuthority(store=store).promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=admission_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:forged",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_scenario_invalid"
    assert store.get_stream_head("gameplay:government:organization:bakery") == 0


def test_government_promotion_rejects_catalog_mismatch_before_production_append(monkeypatch) -> None:
    store, admission_event_id, scenario_event_id = _setup()

    def reject_operation(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_owner_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_operation)

    rejected = GovernmentAuthority(store=store).promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:catalog-mismatch",
        privacy_scope="project",
    )

    assert not rejected.accepted
    assert rejected.error_code == "governed_authority_contract_owner_mismatch"
    assert store.get_stream_head("gameplay:government:organization:bakery") == 0


def test_government_promotion_emits_scoped_outbox_and_replays_production_checkpoint_tail() -> None:
    store, admission_event_id, scenario_event_id = _setup()
    preview = BranchPreviewAuthority(
        store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)
    )
    assert GovernmentAuthority(store=store).promote_branch_inspection(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=0,
        idempotency_key="promotion:government:inspection:replay",
        privacy_scope="project",
    ).accepted

    full = preview.production_replay()
    tail = preview.production_replay(checkpoint_at=0)

    assert full.projection_hash == tail.projection_hash
    assert any(
        entry.topic == "world.government.inspection_projection" and entry.audience == "project"
        for entry in store.list_outbox()
    )
