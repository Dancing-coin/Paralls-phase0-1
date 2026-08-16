from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority, RoleAssignment
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    ReferenceDataset,
)
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _candidate(*, branch_ref: str = "branch:organization:promotion") -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref=f"intent:{branch_ref}:supply",
        profile_ref="character:char_a",
        intent_kind="supply",
        payload={
            "organization_ref": "organization:bakery",
            "counterparty_organization_ref": "organization:supplier",
            "commitment_ref": f"commitment:{branch_ref}",
            "organization_grant_refs": ("grant:promotion",),
            "budget_reservation_refs": ("reservation:promotion",),
        },
        priority=1,
        policy_revision="policy:promotion",
        package_revision="package:promotion",
        idempotency_key=f"candidate:{branch_ref}:supply",
        correlation_id=f"corr:{branch_ref}:supply",
        source_ref="planner",
        privacy_scope="actor:self",
        expected_revisions={"gameplay:organization:organization:bakery": 1},
    )


def _authority() -> tuple[GameplayEventStore, BranchPreviewAuthority, str, str]:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    assert organization.grant_commerce_budget(
        command_id="command:organization:promotion:grant",
        organization_ref="organization:bakery",
        grant_ref="grant:promotion",
        budget_reservation_ref="reservation:promotion",
        amount_minor=100,
        policy_revision="policy:promotion",
        idempotency_key="idempotency:organization:promotion:grant",
        causation_id="cause:organization:promotion:grant",
        correlation_id="corr:organization:promotion:grant",
    ).committed
    authority = BranchPreviewAuthority(
        store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR)
    )
    branch_ref = "branch:organization:promotion"
    candidate = _candidate(branch_ref=branch_ref)
    assert authority.preview(
        request=BranchPreviewRequest(
            branch_ref=branch_ref,
            world_ref="world:bakery",
            base_event_digest="sha256:empty",
            deterministic_seed="seed:organization:promotion",
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
            allowed_intent_kinds=("supply",),
            degraded_threshold=1,
        ),
    ).accepted
    scenario = authority.settle_accepted_supply_scenario(
        branch_ref=branch_ref,
        intent_ref=candidate.intent_ref,
    )
    assert scenario.committed
    admission_stream = authority.admission_stream_id(branch_ref=branch_ref)
    scenario_stream = OrganizationAuthority.branch_scenario_stream_id(
        branch_ref=branch_ref,
        organization_ref="organization:bakery",
    )
    admission_event_id = store.read_stream(admission_stream)[0].event_id
    scenario_event_id = store.read_stream(scenario_stream)[0].event_id
    return store, authority, admission_event_id, scenario_event_id


def test_organization_promotes_one_durable_supply_into_existing_production_stream() -> None:
    store, _, admission_event_id, scenario_event_id = _authority()

    result = OrganizationAuthority(store=store).promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:1",
        privacy_scope="project",
    )

    assert result.accepted
    assert result.receipt is not None
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 2
    event = store.read_stream("gameplay:organization:organization:bakery")[-1]
    assert event.event_type == "gameplay.organization.commerce_commitment_accepted"
    assert event.visibility_policy == "project"
    assert event.payload["branch_admission_event_id"] == admission_event_id
    assert event.payload["branch_scenario_event_id"] == scenario_event_id
    assert event.payload["organization_grant_refs"] == ("grant:promotion",)
    assert event.payload["budget_reservation_refs"] == ("reservation:promotion",)


def test_organization_supply_promotion_exact_duplicate_reconstructs_receipt_without_second_append() -> None:
    store, _, admission_event_id, scenario_event_id = _authority()
    organization = OrganizationAuthority(store=store)

    first = organization.promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:duplicate",
        privacy_scope="project",
    )
    duplicate = organization.promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:duplicate",
        privacy_scope="project",
    )

    assert first.accepted and duplicate.accepted
    assert first.receipt is not None and duplicate.receipt is not None
    assert duplicate.receipt.idempotency_status == "duplicate_replayed"
    assert duplicate.receipt.committed_event_ids == first.receipt.committed_event_ids
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 2


def test_organization_supply_promotion_rejects_changed_duplicate_without_append() -> None:
    store, _, admission_event_id, scenario_event_id = _authority()
    organization = OrganizationAuthority(store=store)
    assert organization.promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:changed",
        privacy_scope="project",
    ).accepted

    rejected = organization.promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=2,
        idempotency_key="promotion:organization:supply:changed",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "idempotency_key_reused"
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 2


def test_organization_supply_promotion_rejects_stale_source_without_append() -> None:
    store, _, admission_event_id, scenario_event_id = _authority()
    organization = OrganizationAuthority(store=store)
    assert organization.settle_role_assignment(
        role=RoleAssignment(
            organization_ref="organization:bakery",
            character_ref="character:char_a",
            role="buyer",
            assignment_ref="assignment:promotion:advance",
        ),
        existing_character_refs={"character:char_a"},
        command_id="command:organization:promotion:advance",
        idempotency_key="idempotency:organization:promotion:advance",
        causation_id="cause:organization:promotion:advance",
        correlation_id="corr:organization:promotion:advance",
    ).committed

    rejected = organization.promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:stale",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_revision_conflict"
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 2


def test_organization_supply_promotion_rejects_wrong_privacy_without_append() -> None:
    store, _, admission_event_id, scenario_event_id = _authority()

    rejected = OrganizationAuthority(store=store).promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:privacy",
        privacy_scope="creator_debug",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_privacy_denied"
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 1


def test_organization_supply_promotion_rejects_forged_source_or_scenario_without_append() -> None:
    store, _, admission_event_id, _ = _authority()

    rejected = OrganizationAuthority(store=store).promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=admission_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:forged",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_scenario_invalid"
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 1


def test_organization_supply_promotion_rejects_forged_admission_without_append() -> None:
    store, _, admission_event_id, scenario_event_id = _authority()

    rejected = OrganizationAuthority(store=store).promote_branch_supply(
        admission_event_id=scenario_event_id,
        scenario_event_id=admission_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:forged-admission",
        privacy_scope="project",
    )

    assert not rejected.accepted and rejected.error_code == "branch_promotion_admission_invalid"
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 1


def test_organization_supply_promotion_full_and_checkpoint_tail_replay_match() -> None:
    store, authority, admission_event_id, scenario_event_id = _authority()
    assert OrganizationAuthority(store=store).promote_branch_supply(
        admission_event_id=admission_event_id,
        scenario_event_id=scenario_event_id,
        expected_production_revision=1,
        idempotency_key="promotion:organization:supply:replay",
        privacy_scope="project",
    ).accepted

    full = authority.production_replay()
    tail = authority.production_replay(checkpoint_at=0)

    assert full.projection_hash == tail.projection_hash
    assert any(
        entry.topic == "world.organization.commerce_commitment_projection"
        and entry.audience == "project"
        for entry in store.list_outbox()
    )
