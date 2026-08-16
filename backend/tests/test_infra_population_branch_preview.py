from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    FamilyOrganizationProjectionInput,
    ReferenceDataset,
)
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile
from app.population_continuity.batch import ContinuityMergeAuthority, PopulationPlanner


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _mode() -> WorldModeProfile:
    return WorldModeProfile(world_ref="world:bakery", mode="replay", revision="mode:1", cadence_class="daily", batch_limit=3, wake_budget=3, catch_up_limit=2, allowed_intent_kinds=("work",), degraded_threshold=1)


def _dataset() -> ReferenceDataset:
    return ReferenceDataset(dataset_ref="dataset:prices:1", provenance="fixture", license_ref="license:permitted", schema_revision="1", digest="sha256:dataset", classification="creator_debug", allowed_scopes=("creator_debug",))


def _request() -> BranchPreviewRequest:
    return BranchPreviewRequest(branch_ref="branch:1", world_ref="world:bakery", base_event_digest="sha256:empty", deterministic_seed="seed:1", active_revision_refs=("mode:1",), calibration_ref="calibration:1", privacy_scope="creator_debug")


def test_reference_and_calibration_inputs_are_versioned_and_scoped() -> None:
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    family = FamilyOrganizationProjectionInput(profile_ref="character:char_a", source_projection_ref="projection:family:1", source_revision=1, privacy_scope="organization:summary", digest="sha256:family")
    assert calibration.dataset_ref == _dataset().dataset_ref
    assert family.profile_ref == "character:char_a"


def test_branch_preview_is_deterministic_and_does_not_append_production_events() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    result = authority.preview(request=_request(), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(FamilyOrganizationProjectionInput(profile_ref="character:char_a", source_projection_ref="projection:family:1", source_revision=1, privacy_scope="organization:summary", digest="sha256:family"),), candidates=(BatchIntentCandidate(intent_ref="intent:1", profile_ref="character:char_a", intent_kind="work", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:1", correlation_id="corr:1", source_ref="planner", privacy_scope="actor:self"),), mode=_mode())
    repeated = authority.preview(request=_request(), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(FamilyOrganizationProjectionInput(profile_ref="character:char_a", source_projection_ref="projection:family:1", source_revision=1, privacy_scope="organization:summary", digest="sha256:family"),), candidates=(BatchIntentCandidate(intent_ref="intent:1", profile_ref="character:char_a", intent_kind="work", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:1", correlation_id="corr:1", source_ref="planner", privacy_scope="actor:self"),), mode=_mode())
    assert result.accepted and result.report_digest == repeated.report_digest
    assert store.read_events() == []


def test_branch_preview_rejects_dataset_scope_and_base_mismatch_without_writes() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    bad = authority.preview(request=_request().model_copy(update={"privacy_scope": "public"}), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(), candidates=(), mode=_mode())
    assert not bad.accepted and bad.error_code == "dataset_scope_denied"
    assert store.read_events() == []


def test_branch_report_redacts_public_data_and_production_replay_remains_equivalent() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    result = authority.preview(request=_request(), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(), candidates=(), mode=_mode())
    assert result.public_report["family_inputs"] == ()
    assert authority.production_replay().projection_hash == authority.production_replay(checkpoint_at=0).projection_hash


def test_branch_buffer_replays_deterministically_without_production_append() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    authority.preview(request=_request(), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(), mode=_mode())
    first = authority.branch_replay_digest("branch:1")
    authority.preview(request=_request(), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(), mode=_mode())
    assert authority.branch_replay_digest("branch:1") == first
    assert store.read_events() == []


def test_isolated_branch_events_rebuild_projection_and_checkpoint_tail_without_production_append() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    candidates = (
        BatchIntentCandidate(intent_ref="intent:branch:a", profile_ref="character:char_a", intent_kind="work", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:a", correlation_id="corr:branch:a", source_ref="planner", privacy_scope="actor:self"),
        BatchIntentCandidate(intent_ref="intent:branch:b", profile_ref="character:char_b", intent_kind="work", payload={}, priority=2, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:b", correlation_id="corr:branch:b", source_ref="planner", privacy_scope="actor:self"),
    )

    result = authority.preview(request=_request(), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=candidates, mode=_mode())
    full = authority.branch_projection("branch:1")
    tail = authority.branch_projection("branch:1", checkpoint_at=1)
    promotion = authority.promote("branch:1")

    assert result.accepted is True and result.branch_event_count == 7
    assert full["candidate_intent_refs"] == ("intent:branch:b", "intent:branch:a")
    assert full["blocked_owner_intent_refs"] == ("intent:branch:b", "intent:branch:a")
    assert full["rejected_owner_consequence_intent_refs"] == ("intent:branch:b", "intent:branch:a")
    assert full["projection_hash"] == tail["projection_hash"]
    assert promotion.accepted is False and promotion.error_code == "branch_promotion_unsupported"
    assert store.read_events() == [] and store.list_outbox() == []


def test_production_batch_duplicate_revision_conflict_and_checkpoint_tail_are_explicit() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    candidate = BatchIntentCandidate(
        intent_ref="intent:production:1", profile_ref="character:char_a", intent_kind="work",
        payload={"stream_ref": "population:character:char_a", "event_type": "population.intent.proposed"}, priority=1,
        expected_revisions={"population:character:char_a": 0}, policy_revision="mode:1", package_revision="package:1",
        idempotency_key="intent:production:1", correlation_id="corr:production:1", source_ref="planner", privacy_scope="actor:self",
    )
    planner = PopulationPlanner()
    plan = planner.plan(batch_ref="batch:production:1", world_ref="world:bakery", mode=_mode(), candidates=(candidate,), input_digest="sha256:production", deterministic_seed="seed:production")
    authority = ContinuityMergeAuthority(store=store, registry=registry, mode=_mode())
    first = authority.merge(plan)
    duplicate = authority.merge(plan)
    assert first.zero_write and duplicate.zero_write
    assert first.stop_reason == duplicate.stop_reason == "legacy_population_merge_retired"
    conflicting = planner.plan(
        batch_ref="batch:production:2", world_ref="world:bakery", mode=_mode(),
        candidates=(candidate.model_copy(update={"intent_ref": "intent:production:2", "idempotency_key": "intent:production:2"}),), input_digest="sha256:production:2", deterministic_seed="seed:production",
    )
    rejected = authority.merge(conflicting)
    assert not rejected.committed and rejected.stop_reason == "legacy_population_merge_retired"
    assert store.read_events() == []
    branch_authority = BranchPreviewAuthority(store=store, registry=registry)
    assert branch_authority.production_replay().projection_hash == branch_authority.production_replay(checkpoint_at=1).projection_hash


def test_inf4z_branch_preview_request_pins_fixed_base_checkpoint_tail_and_source_digests() -> None:
    request = BranchPreviewRequest(
        branch_ref="branch:inf4z:1",
        world_ref="world:bakery",
        base_event_digest="sha256:base",
        deterministic_seed="seed:inf4z",
        active_revision_refs=("mode:1", "policy:1"),
        calibration_ref="calibration:1",
        privacy_scope="creator_debug",
        base_checkpoint_sequence=3,
        tail_boundary=5,
        source_digests={
            "social": "sha256:social",
            "household": "sha256:household",
            "organization": "sha256:organization",
            "calibration": "sha256:calibration",
        },
    )

    assert request.base_checkpoint_sequence == 3
    assert request.tail_boundary == 5
    assert request.source_digests["organization"] == "sha256:organization"


def test_inf4z_branch_preview_rejects_fixed_base_digest_mismatch_without_production_writes() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))

    result = authority.preview(
        request=_request().model_copy(
            update={
                "base_checkpoint_sequence": 0,
                "tail_boundary": 0,
                "source_digests": {"calibration": "sha256:wrong"},
            }
        ),
        dataset=_dataset(),
        calibration=CalibrationInput(
            calibration_ref="calibration:1",
            dataset_ref="dataset:prices:1",
            parameter_mapping_revision="map:1",
            world_revision="world:1",
            ruleset_revision="rules:1",
            privacy_scope="creator_debug",
        ),
        family_inputs=(),
        candidates=(),
        mode=_mode(),
    )

    assert result.accepted is False
    assert result.error_code == "branch_source_digest_mismatch"
    assert store.read_events() == []


def test_fixed_base_branch_replay_pins_checkpoint_tail_and_source_digests() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    request = _request().model_copy(update={
        "base_checkpoint_sequence": 0,
        "tail_boundary": 0,
        "source_digests": {"organization": "sha256:organization"},
    })
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")

    result = authority.preview(request=request, dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(), mode=_mode())
    repeated = authority.preview(request=request, dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(), mode=_mode())

    assert result.accepted is True
    assert result.report_digest == repeated.report_digest
    assert store.read_events() == []


def test_fixed_base_branch_rejects_tail_beyond_production_without_writes() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    request = _request().model_copy(update={"tail_boundary": 1})
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")

    result = authority.preview(request=request, dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(), mode=_mode())

    assert result.accepted is False
    assert result.error_code == "branch_tail_boundary_mismatch"
    assert store.read_events() == []


def test_inf4z_branch_preview_orders_shuffled_candidates_deterministically() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    candidate_a = BatchIntentCandidate(intent_ref="intent:preview:a", profile_ref="character:char_a", intent_kind="work", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:preview:a", correlation_id="corr:preview:a", source_ref="planner", privacy_scope="actor:self")
    candidate_b = BatchIntentCandidate(intent_ref="intent:preview:b", profile_ref="character:char_b", intent_kind="work", payload={}, priority=2, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:preview:b", correlation_id="corr:preview:b", source_ref="planner", privacy_scope="actor:self")

    first = authority.preview(request=_request(), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(candidate_a, candidate_b), mode=_mode())
    first_digest = authority.branch_replay_digest("branch:1")
    second = authority.preview(request=_request(), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(candidate_b, candidate_a), mode=_mode())

    assert first.accepted is True
    assert second.accepted is True
    assert authority.branch_replay_digest("branch:1") == first_digest
    assert store.read_events() == []


def test_inf4z_branch_preview_rejects_fixed_base_digest_without_production_writes() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")

    result = authority.preview(request=_request().model_copy(update={"base_event_digest": "sha256:wrong"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(), mode=_mode())

    assert result.accepted is False
    assert result.error_code == "branch_base_mismatch"
    assert store.read_events() == []


def test_inf4z_branch_preview_rejects_unknown_candidate_profile_without_production_writes() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    unknown = BatchIntentCandidate(intent_ref="intent:preview:unknown", profile_ref="character:unknown", intent_kind="work", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:preview:unknown", correlation_id="corr:preview:unknown", source_ref="planner", privacy_scope="actor:self")

    result = authority.preview(request=_request(), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(unknown,), mode=_mode())

    assert result.accepted is False
    assert result.error_code == "profile_not_registered"
    assert store.read_events() == []


def test_isolated_branch_projection_records_existing_owner_dispositions_without_production_writes() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    supply = BatchIntentCandidate(intent_ref="intent:branch:supply", profile_ref="character:char_a", intent_kind="supply", payload={}, priority=2, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:supply", correlation_id="corr:branch:supply", source_ref="planner", privacy_scope="actor:self")
    work = BatchIntentCandidate(intent_ref="intent:branch:work", profile_ref="character:char_b", intent_kind="work", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:work", correlation_id="corr:branch:work", source_ref="planner", privacy_scope="actor:self")

    result = authority.preview(request=_request().model_copy(update={"branch_ref": "branch:owner-disposition"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(work, supply), mode=_mode())
    projection = authority.branch_projection("branch:owner-disposition")

    assert result.accepted is True
    assert projection["admitted_owner_intent_refs"] == ("intent:branch:supply",)
    assert projection["blocked_owner_intent_refs"] == ("intent:branch:work",)
    assert store.read_events() == []


def test_isolated_branch_owner_disposition_checkpoint_tail_matches_full_projection() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    inspection = BatchIntentCandidate(intent_ref="intent:branch:inspection", profile_ref="character:char_a", intent_kind="inspection", payload={}, priority=1, policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:inspection", correlation_id="corr:branch:inspection", source_ref="planner", privacy_scope="actor:self")
    authority.preview(request=_request().model_copy(update={"branch_ref": "branch:owner-replay"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(inspection,), mode=_mode())

    full = authority.branch_projection("branch:owner-replay")
    tail = authority.branch_projection("branch:owner-replay", checkpoint_at=2)

    assert full["projection_hash"] == tail["projection_hash"]
    assert full["admitted_owner_intent_refs"] == ("intent:branch:inspection",)


def test_isolated_branch_evaluates_registered_owner_fragment_without_production_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    supply = BatchIntentCandidate(
        intent_ref="intent:branch:consequence:supply", profile_ref="character:char_a", intent_kind="supply",
        payload={"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": "commitment:branch:one", "organization_grant_refs": [], "budget_reservation_refs": []},
        expected_revisions={"gameplay:organization:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:consequence:supply", correlation_id="corr:branch:consequence", source_ref="planner", privacy_scope="actor:self",
    )

    result = authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:supply"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(supply,), mode=_mode())
    projection = authority.branch_projection("branch:consequence:supply")

    assert result.accepted is True
    assert projection["accepted_owner_consequence_intent_refs"] == ("intent:branch:consequence:supply",)
    assert projection["owner_consequence_digests"]["intent:branch:consequence:supply"].startswith("sha256:")
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_isolated_branch_owner_fragment_rejection_and_stale_revision_are_zero_production_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    invalid = BatchIntentCandidate(
        intent_ref="intent:branch:consequence:invalid", profile_ref="character:char_a", intent_kind="supply",
        payload={"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": ""},
        expected_revisions={"gameplay:organization:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:consequence:invalid", correlation_id="corr:branch:invalid", source_ref="planner", privacy_scope="actor:self",
    )
    stale = invalid.model_copy(update={"intent_ref": "intent:branch:consequence:stale", "payload": {"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": "commitment:stale", "organization_grant_refs": [], "budget_reservation_refs": []}, "expected_revisions": {"gameplay:organization:organization:bakery": 1}})

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:rejected"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(invalid, stale), mode=_mode()).accepted
    projection = authority.branch_projection("branch:consequence:rejected")

    assert projection["rejected_owner_consequence_intent_refs"] == ("intent:branch:consequence:invalid", "intent:branch:consequence:stale")
    assert store.read_events() == []
    assert store.list_outbox() == []


def test_isolated_branch_projects_validated_supply_and_inspection_consequences_without_production_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    supply = BatchIntentCandidate(
        intent_ref="intent:branch:projection:supply", profile_ref="character:char_a", intent_kind="supply",
        payload={"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": "commitment:branch:projection", "organization_grant_refs": [], "budget_reservation_refs": []},
        expected_revisions={"gameplay:organization:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:supply", correlation_id="corr:branch:projection:supply", source_ref="planner", privacy_scope="actor:self",
    )
    inspection = BatchIntentCandidate(
        intent_ref="intent:branch:projection:inspection", profile_ref="character:char_b", intent_kind="inspection",
        payload={"organization_ref": "organization:bakery", "inspection_ref": "inspection:branch:projection", "jurisdiction_ref": "jurisdiction:bakery", "policy_digest": "sha256:branch-policy", "evidence_ref": "evidence:branch:inspection", "passed": True},
        expected_revisions={"gameplay:government:organization:bakery": 0}, priority=2,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:inspection", correlation_id="corr:branch:projection:inspection", source_ref="planner", privacy_scope="actor:self",
    )

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:projection"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(supply, inspection), mode=_mode()).accepted
    projection = authority.branch_projection("branch:consequence:projection")
    replay = authority.branch_projection("branch:consequence:projection", checkpoint_at=3)

    assert projection["planned_commitments"] == ({"commitment_ref": "commitment:branch:projection", "organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "policy_revision": "mode:1"},)
    assert projection["planned_inspections"] == ({"inspection_ref": "inspection:branch:projection", "organization_ref": "organization:bakery", "jurisdiction_ref": "jurisdiction:bakery", "passed": True, "policy_revision": "mode:1"},)
    assert projection["projection_hash"] == replay["projection_hash"]
    assert store.read_events() == [] and store.list_outbox() == []


def test_isolated_branch_does_not_project_rejected_owner_consequence() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    calibration = CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug")
    invalid = BatchIntentCandidate(
        intent_ref="intent:branch:projection:invalid", profile_ref="character:char_a", intent_kind="supply",
        payload={"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": ""},
        expected_revisions={"gameplay:organization:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:invalid", correlation_id="corr:branch:projection:invalid", source_ref="planner", privacy_scope="actor:self",
    )

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:no-projection"}), dataset=_dataset(), calibration=calibration, family_inputs=(), candidates=(invalid,), mode=_mode()).accepted
    projection = authority.branch_projection("branch:consequence:no-projection")

    assert projection["rejected_owner_consequence_intent_refs"] == ("intent:branch:projection:invalid",)
    assert projection["planned_commitments"] == ()
    assert projection["planned_inspections"] == ()
    assert store.read_events() == [] and store.list_outbox() == []


def test_isolated_branch_projects_supply_consequence_without_production_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    supply = BatchIntentCandidate(
        intent_ref="intent:branch:projection:supply-only", profile_ref="character:char_a", intent_kind="supply",
        payload={"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": "commitment:branch:supply-only", "organization_grant_refs": [], "budget_reservation_refs": []},
        expected_revisions={"gameplay:organization:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:supply-only", correlation_id="corr:branch:projection:supply-only", source_ref="planner", privacy_scope="actor:self",
    )

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:supply-only"}), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(), candidates=(supply,), mode=_mode()).accepted
    projection = authority.branch_projection("branch:consequence:supply-only")

    assert projection["planned_commitments"] == ({"commitment_ref": "commitment:branch:supply-only", "organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "policy_revision": "mode:1"},)
    assert projection["planned_inspections"] == ()
    assert store.read_events() == [] and store.list_outbox() == []


def test_isolated_branch_projects_inspection_consequence_without_production_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    inspection = BatchIntentCandidate(
        intent_ref="intent:branch:projection:inspection-only", profile_ref="character:char_b", intent_kind="inspection",
        payload={"organization_ref": "organization:bakery", "inspection_ref": "inspection:branch:inspection-only", "jurisdiction_ref": "jurisdiction:bakery", "policy_digest": "sha256:branch-policy", "evidence_ref": "evidence:branch:inspection", "passed": True},
        expected_revisions={"gameplay:government:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:inspection-only", correlation_id="corr:branch:projection:inspection-only", source_ref="planner", privacy_scope="actor:self",
    )

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:inspection-only"}), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(), candidates=(inspection,), mode=_mode()).accepted
    projection = authority.branch_projection("branch:consequence:inspection-only")

    assert projection["planned_commitments"] == ()
    assert projection["planned_inspections"] == ({"inspection_ref": "inspection:branch:inspection-only", "organization_ref": "organization:bakery", "jurisdiction_ref": "jurisdiction:bakery", "passed": True, "policy_revision": "mode:1"},)
    assert store.read_events() == [] and store.list_outbox() == []


def test_isolated_branch_consequence_projection_redacts_owner_only_references() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    inspection = BatchIntentCandidate(
        intent_ref="intent:branch:projection:redacted", profile_ref="character:char_a", intent_kind="inspection",
        payload={"organization_ref": "organization:bakery", "inspection_ref": "inspection:branch:redacted", "jurisdiction_ref": "jurisdiction:bakery", "policy_digest": "sha256:branch-policy", "evidence_ref": "evidence:owner-only", "passed": True},
        expected_revisions={"gameplay:government:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:redacted", correlation_id="corr:branch:projection:redacted", source_ref="planner", privacy_scope="actor:self",
    )

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:redacted"}), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(), candidates=(inspection,), mode=_mode()).accepted
    projection = authority.branch_projection("branch:consequence:redacted")

    assert projection["planned_inspections"] == ({"inspection_ref": "inspection:branch:redacted", "organization_ref": "organization:bakery", "jurisdiction_ref": "jurisdiction:bakery", "passed": True, "policy_revision": "mode:1"},)
    assert "evidence:owner-only" not in repr(projection)


def test_isolated_branch_consequence_projection_promotion_remains_unsupported() -> None:
    promotion = BranchPreviewAuthority.promote("branch:consequence:non-promotable")

    assert promotion.accepted is False
    assert promotion.error_code == "branch_promotion_unsupported"


def test_isolated_branch_consequence_projection_checkpoint_tail_matches_full() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    supply = BatchIntentCandidate(
        intent_ref="intent:branch:projection:replay", profile_ref="character:char_a", intent_kind="supply",
        payload={"organization_ref": "organization:bakery", "counterparty_organization_ref": "organization:supplier", "commitment_ref": "commitment:branch:replay", "organization_grant_refs": [], "budget_reservation_refs": []},
        expected_revisions={"gameplay:organization:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:projection:replay", correlation_id="corr:branch:projection:replay", source_ref="planner", privacy_scope="actor:self",
    )

    assert authority.preview(request=_request().model_copy(update={"branch_ref": "branch:consequence:replay"}), dataset=_dataset(), calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"), family_inputs=(), candidates=(supply,), mode=_mode()).accepted

    assert authority.branch_projection("branch:consequence:replay")["projection_hash"] == authority.branch_projection("branch:consequence:replay", checkpoint_at=3)["projection_hash"]
    assert store.read_events() == [] and store.list_outbox() == []


def test_durable_isolated_branch_snapshot_rebuilds_in_fresh_authority_without_production_event() -> None:
    store = GameplayEventStore()
    registry = CharacterProfileRegistry.from_directory(PROFILE_DIR)
    authority = BranchPreviewAuthority(store=store, registry=registry)
    branch_ref = "branch:durable:snapshot"
    assert authority.preview(
        request=_request().model_copy(update={"branch_ref": branch_ref}),
        dataset=_dataset(),
        calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(),
        candidates=(),
        mode=_mode(),
    ).accepted
    in_memory = authority.branch_projection(branch_ref)

    recorded = authority.record_isolated_branch_snapshot(
        branch_ref=branch_ref,
        expected_revision=0,
        idempotency_key="branch:durable:snapshot",
        privacy_scope="creator_debug",
    )
    rebuilt = BranchPreviewAuthority(store=store, registry=registry).durable_branch_projection(branch_ref)

    assert recorded.committed
    assert [event.event_type for event in store.read_events()] == ["gameplay.branch_preview.isolated_snapshot_recorded"]
    assert {entry.audience for entry in store.list_outbox()} == {"creator_debug"}
    assert rebuilt["projection_hash"] == in_memory["projection_hash"]
    assert BranchPreviewAuthority(store=store, registry=registry).production_replay().projection_hash == BranchPreviewAuthority(store=store, registry=registry).production_replay(checkpoint_at=0).projection_hash


def test_durable_isolated_branch_snapshot_rejects_missing_buffer_or_wrong_scope_without_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    before = store.export_snapshot()

    missing = authority.record_isolated_branch_snapshot(
        branch_ref="branch:missing",
        expected_revision=0,
        idempotency_key="branch:missing",
        privacy_scope="creator_debug",
    )
    wrong_scope = authority.record_isolated_branch_snapshot(
        branch_ref="branch:missing",
        expected_revision=0,
        idempotency_key="branch:missing:scope",
        privacy_scope="project",
    )

    assert missing.committed is False and missing.failure is not None and missing.failure.error_code == "branch_snapshot_buffer_missing"
    assert wrong_scope.committed is False and wrong_scope.failure is not None and wrong_scope.failure.error_code == "branch_snapshot_privacy_denied"
    assert store.export_snapshot() == before


def test_durable_isolated_branch_snapshot_is_idempotent_and_rejects_stale_revision_without_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    branch_ref = "branch:durable:idempotency"
    assert authority.preview(
        request=_request().model_copy(update={"branch_ref": branch_ref}), dataset=_dataset(),
        calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(), candidates=(), mode=_mode(),
    ).accepted
    first = authority.record_isolated_branch_snapshot(branch_ref=branch_ref, expected_revision=0, idempotency_key="branch:durable:idempotency", privacy_scope="creator_debug")
    duplicate = authority.record_isolated_branch_snapshot(branch_ref=branch_ref, expected_revision=0, idempotency_key="branch:durable:idempotency", privacy_scope="creator_debug")
    before_stale = store.export_snapshot()
    stale = authority.record_isolated_branch_snapshot(branch_ref=branch_ref, expected_revision=0, idempotency_key="branch:durable:stale", privacy_scope="creator_debug")

    assert first.committed and duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert stale.committed is False and stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert store.export_snapshot() == before_stale


def test_durable_isolated_branch_snapshot_rejects_second_snapshot_without_write() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    branch_ref = "branch:durable:single-snapshot"
    assert authority.preview(
        request=_request().model_copy(update={"branch_ref": branch_ref}), dataset=_dataset(),
        calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(), candidates=(), mode=_mode(),
    ).accepted
    assert authority.record_isolated_branch_snapshot(branch_ref=branch_ref, expected_revision=0, idempotency_key="branch:durable:single:first", privacy_scope="creator_debug").committed
    before = store.export_snapshot()
    second = authority.record_isolated_branch_snapshot(branch_ref=branch_ref, expected_revision=1, idempotency_key="branch:durable:single:second", privacy_scope="creator_debug")

    assert second.committed is False and second.failure is not None and second.failure.error_code == "branch_snapshot_already_recorded"
    assert store.export_snapshot() == before


def test_durable_isolated_branch_snapshot_is_redacted_and_checkpoint_tail_replayable() -> None:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    branch_ref = "branch:durable:redacted"
    inspection = BatchIntentCandidate(
        intent_ref="intent:branch:durable:redacted", profile_ref="character:char_a", intent_kind="inspection",
        payload={"organization_ref": "organization:bakery", "inspection_ref": "inspection:branch:durable", "jurisdiction_ref": "jurisdiction:bakery", "policy_digest": "sha256:branch-policy", "evidence_ref": "evidence:durable-owner-only", "passed": True},
        expected_revisions={"gameplay:government:organization:bakery": 0}, priority=1,
        policy_revision="mode:1", package_revision="package:1", idempotency_key="intent:branch:durable:redacted", correlation_id="corr:branch:durable:redacted", source_ref="planner", privacy_scope="actor:self",
    )
    assert authority.preview(
        request=_request().model_copy(update={"branch_ref": branch_ref}), dataset=_dataset(),
        calibration=CalibrationInput(calibration_ref="calibration:1", dataset_ref="dataset:prices:1", parameter_mapping_revision="map:1", world_revision="world:1", ruleset_revision="rules:1", privacy_scope="creator_debug"),
        family_inputs=(), candidates=(inspection,), mode=_mode(),
    ).accepted
    assert authority.record_isolated_branch_snapshot(branch_ref=branch_ref, expected_revision=0, idempotency_key="branch:durable:redacted", privacy_scope="creator_debug").committed
    fresh = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    full = fresh.durable_branch_projection(branch_ref)
    checkpoint_tail = fresh.durable_branch_projection(branch_ref, checkpoint_at=3)

    assert full["projection_hash"] == checkpoint_tail["projection_hash"]
    assert "evidence:durable-owner-only" not in repr(store.read_events()[0].payload)
    assert full["planned_inspections"] == ({"inspection_ref": "inspection:branch:durable", "organization_ref": "organization:bakery", "jurisdiction_ref": "jurisdiction:bakery", "passed": True, "policy_revision": "mode:1"},)
