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


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="preview",
        revision="mode:1",
        cadence_class="daily",
        batch_limit=3,
        wake_budget=3,
        catch_up_limit=2,
        allowed_intent_kinds=("supply",),
        degraded_threshold=1,
    )


def _request() -> BranchPreviewRequest:
    return BranchPreviewRequest(
        branch_ref="branch:scenario:1",
        world_ref="world:bakery",
        base_event_digest="sha256:empty",
        deterministic_seed="seed:scenario:1",
        active_revision_refs=("mode:1",),
        calibration_ref="calibration:1",
        privacy_scope="creator_debug",
    )


def _dataset() -> ReferenceDataset:
    return ReferenceDataset(
        dataset_ref="dataset:prices:scenario",
        provenance="fixture",
        license_ref="license:permitted",
        schema_revision="1",
        digest="sha256:dataset:scenario",
        classification="creator_debug",
        allowed_scopes=("creator_debug",),
    )


def _calibration() -> CalibrationInput:
    return CalibrationInput(
        calibration_ref="calibration:1",
        dataset_ref="dataset:prices:scenario",
        parameter_mapping_revision="map:1",
        world_revision="world:1",
        ruleset_revision="rules:1",
        privacy_scope="creator_debug",
    )


def _supply() -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref="intent:branch:scenario:supply",
        profile_ref="character:char_a",
        intent_kind="supply",
        payload={
            "organization_ref": "organization:bakery",
            "counterparty_organization_ref": "organization:supplier",
            "commitment_ref": "commitment:branch:scenario",
            "organization_grant_refs": [],
            "budget_reservation_refs": [],
        },
        priority=1,
        policy_revision="mode:1",
        package_revision="package:1",
        idempotency_key="intent:branch:scenario:supply",
        correlation_id="corr:branch:scenario:supply",
        source_ref="planner",
        privacy_scope="actor:self",
        expected_revisions={"gameplay:organization:organization:bakery": 0},
    )


def _authority() -> tuple[GameplayEventStore, BranchPreviewAuthority]:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    assert authority.preview(
        request=_request(),
        dataset=_dataset(),
        calibration=_calibration(),
        family_inputs=(),
        candidates=(_supply(),),
        mode=_mode(),
    ).accepted
    return store, authority


def test_accepted_supply_branch_proposal_settles_on_organization_scenario_stream() -> None:
    store, authority = _authority()

    receipt = authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply")

    assert receipt.committed
    assert store.get_stream_head("gameplay:organization_branch:branch:scenario:1:organization:bakery") == 1
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 0
    assert authority.branch_scenario_projection("branch:scenario:1", organization_ref="organization:bakery")["commitment_refs"] == ("commitment:branch:scenario",)


def test_branch_scenario_duplicate_idempotency_replays_without_second_append() -> None:
    store, authority = _authority()
    first = authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply")
    duplicate = authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply")

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.get_stream_head("gameplay:organization_branch:branch:scenario:1:organization:bakery") == 1


def test_branch_scenario_duplicate_retry_replays_after_production_source_advances() -> None:
    store, authority = _authority()
    first = authority.settle_accepted_supply_scenario(
        branch_ref="branch:scenario:1",
        intent_ref="intent:branch:scenario:supply",
        idempotency_key="scenario:retry-after-source-advance",
    )
    advance = OrganizationAuthority(store=store).settle_role_assignment(
        RoleAssignment(
            organization_ref="organization:bakery",
            character_ref="character:char_a",
            role="buyer",
            assignment_ref="assignment:scenario:retry-after-source-advance",
        ),
        existing_character_refs={"character:char_a"},
        command_id="command:organization:retry-after-source-advance",
        idempotency_key="idem:organization:retry-after-source-advance",
        causation_id="cause:organization:retry-after-source-advance",
        correlation_id="corr:organization:retry-after-source-advance",
    )
    duplicate = authority.settle_accepted_supply_scenario(
        branch_ref="branch:scenario:1",
        intent_ref="intent:branch:scenario:supply",
        idempotency_key="scenario:retry-after-source-advance",
    )

    assert first.committed and advance.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.get_stream_head("gameplay:organization_branch:branch:scenario:1:organization:bakery") == 1
    assert store.get_stream_head("gameplay:organization:organization:bakery") == 1


def test_branch_scenario_changed_duplicate_payload_rejects_without_append() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_supply_scenario(
        branch_ref="branch:scenario:1",
        intent_ref="intent:branch:scenario:supply",
        idempotency_key="scenario:shared",
    ).committed
    assert authority.preview(
        request=_request().model_copy(update={"branch_ref": "branch:scenario:2"}),
        dataset=_dataset(),
        calibration=_calibration(),
        family_inputs=(),
        candidates=(_supply(),),
        mode=_mode(),
    ).accepted

    rejected = authority.settle_accepted_supply_scenario(
        branch_ref="branch:scenario:2",
        intent_ref="intent:branch:scenario:supply",
        idempotency_key="scenario:shared",
    )

    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "idempotency_key_reused"
    assert store.get_stream_head("gameplay:organization_branch:branch:scenario:1:organization:bakery") == 1
    assert store.get_stream_head("gameplay:organization_branch:branch:scenario:2:organization:bakery") == 0


def test_branch_scenario_rejects_non_creator_privacy_without_append() -> None:
    store, authority = _authority()

    rejected = authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply", privacy_scope="public")

    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "branch_scenario_privacy_denied"
    assert store.read_events() == []


def test_branch_scenario_rejects_unknown_candidate_without_append() -> None:
    store, authority = _authority()

    rejected = authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="missing")

    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "branch_scenario_candidate_unavailable"
    assert store.read_events() == []


def test_branch_scenario_rejects_stale_scenario_revision_without_append() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply").committed

    rejected = authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply", idempotency_key="scenario:stale", expected_revision=0)

    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "revision_conflict"
    assert store.get_stream_head("gameplay:organization_branch:branch:scenario:1:organization:bakery") == 1


def test_branch_scenario_checkpoint_tail_replay_matches_full() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply").committed

    full = authority.branch_scenario_projection("branch:scenario:1", organization_ref="organization:bakery")
    tail = authority.branch_scenario_projection("branch:scenario:1", organization_ref="organization:bakery", checkpoint_at=0)

    assert full["projection_hash"] == tail["projection_hash"]


def test_branch_scenario_does_not_change_production_replay() -> None:
    store, authority = _authority()
    production_before = authority.production_replay().projection_hash
    assert authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply").committed

    assert authority.production_replay().projection_hash == production_before


def test_branch_scenario_promotion_remains_unsupported() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply").committed

    promotion = authority.promote("branch:scenario:1")

    assert promotion.accepted is False and promotion.error_code == "branch_promotion_unsupported"


def test_branch_scenario_emits_only_scoped_scenario_outbox() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_supply_scenario(branch_ref="branch:scenario:1", intent_ref="intent:branch:scenario:supply").committed

    assert any(entry.topic == "world.organization_branch.scenario_projection" for entry in store.list_outbox())
