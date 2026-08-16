from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.population_continuity.branch_preview import (
    BranchPreviewAuthority,
    BranchPreviewRequest,
    CalibrationInput,
    ReferenceDataset,
)
from app.population_continuity.branch_replay_contract import FixedBaseBranchReplayContract
from app.population_continuity.models import BatchIntentCandidate, WorldModeProfile


PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world:bakery",
        mode="replay",
        revision="mode:c5",
        cadence_class="daily",
        batch_limit=2,
        wake_budget=2,
        catch_up_limit=1,
        allowed_intent_kinds=("work",),
        degraded_threshold=1,
    )


def _dataset() -> ReferenceDataset:
    return ReferenceDataset(
        dataset_ref="dataset:prices:c5",
        provenance="fixture",
        license_ref="license:permitted",
        schema_revision="1",
        digest="sha256:dataset-c5",
        classification="creator_debug",
        allowed_scopes=("creator_debug",),
    )


def _calibration() -> CalibrationInput:
    return CalibrationInput(
        calibration_ref="calibration:c5",
        dataset_ref="dataset:prices:c5",
        parameter_mapping_revision="map:c5",
        world_revision="world:c5",
        ruleset_revision="rules:c5",
        privacy_scope="creator_debug",
    )


def _request(*, branch_ref: str = "branch:c5") -> BranchPreviewRequest:
    return BranchPreviewRequest(
        branch_ref=branch_ref,
        world_ref="world:bakery",
        base_event_digest="sha256:empty",
        base_checkpoint_sequence=0,
        tail_boundary=0,
        source_digests={},
        deterministic_seed="seed:c5",
        calibration_ref="calibration:c5",
        privacy_scope="creator_debug",
    )


def _candidate(*, intent_ref: str, priority: int) -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref=intent_ref,
        profile_ref="character:char_a",
        intent_kind="work",
        payload={},
        priority=priority,
        policy_revision="mode:c5",
        package_revision="package:c5",
        idempotency_key=intent_ref,
        correlation_id=f"corr:{intent_ref}",
        source_ref="planner",
        privacy_scope="actor:self",
    )


def _authority(store: GameplayEventStore) -> BranchPreviewAuthority:
    return BranchPreviewAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
    )


def test_c5_contract_canonicalizes_fixed_base_source_and_candidate_ordering() -> None:
    first = FixedBaseBranchReplayContract.from_preview_inputs(
        branch_ref="branch:c5",
        base_event_digest="sha256:empty",
        base_checkpoint_sequence=0,
        tail_boundary=0,
        calibration_ref="calibration:c5",
        calibration=_calibration().model_dump(mode="json"),
        source_digests={"organization": "sha256:organization", "calibration": "sha256:calibration"},
        candidate_digests=(("intent:b", "sha256:b"), ("intent:a", "sha256:a")),
        family_digests=("sha256:family",),
        dataset_digest="sha256:dataset-c5",
        privacy_scope="creator_debug",
    )
    second = FixedBaseBranchReplayContract.from_preview_inputs(
        branch_ref="branch:c5",
        base_event_digest="sha256:empty",
        base_checkpoint_sequence=0,
        tail_boundary=0,
        calibration_ref="calibration:c5",
        calibration=_calibration().model_dump(mode="json"),
        source_digests={"calibration": "sha256:calibration", "organization": "sha256:organization"},
        candidate_digests=(("intent:a", "sha256:a"), ("intent:b", "sha256:b")),
        family_digests=("sha256:family",),
        dataset_digest="sha256:dataset-c5",
        privacy_scope="creator_debug",
    )

    assert first.input_digest == second.input_digest
    assert first.source_digests == (("calibration", "sha256:calibration"), ("organization", "sha256:organization"))
    assert first.candidate_digests == (("intent:a", "sha256:a"), ("intent:b", "sha256:b"))


def test_c5_preview_rejects_wrong_fixed_base_without_any_write() -> None:
    store = GameplayEventStore()
    authority = _authority(store)
    before = store.export_snapshot()

    result = authority.preview(
        request=_request().model_copy(update={"base_event_digest": "sha256:wrong"}),
        dataset=_dataset(),
        calibration=_calibration(),
        family_inputs=(),
        candidates=(),
        mode=_mode(),
    )

    assert result.accepted is False
    assert result.error_code == "branch_base_mismatch"
    assert store.export_snapshot() == before


def test_c5_preview_rejects_wrong_calibration_digest_without_any_write() -> None:
    store = GameplayEventStore()
    authority = _authority(store)
    before = store.export_snapshot()

    result = authority.preview(
        request=_request().model_copy(update={"source_digests": {"calibration": "sha256:wrong"}}),
        dataset=_dataset(),
        calibration=_calibration(),
        family_inputs=(),
        candidates=(),
        mode=_mode(),
    )

    assert result.accepted is False
    assert result.error_code == "branch_source_digest_mismatch"
    assert store.export_snapshot() == before


def test_c5_contract_rejects_cross_branch_stream_without_any_write() -> None:
    store = GameplayEventStore()
    contract = FixedBaseBranchReplayContract.from_preview_inputs(
        branch_ref="branch:c5",
        base_event_digest="sha256:empty",
        base_checkpoint_sequence=0,
        tail_boundary=0,
        calibration_ref="calibration:c5",
        calibration=_calibration().model_dump(mode="json"),
        source_digests={},
        candidate_digests=(),
        family_digests=(),
        dataset_digest="sha256:dataset-c5",
        privacy_scope="creator_debug",
    )
    before = store.export_snapshot()

    error = contract.validate_branch_stream(
        stream_id="gameplay:branch_preview:branch:other",
        branch_ref="branch:c5",
        privacy_scope="creator_debug",
    )

    assert error == "branch_replay_stream_mismatch"
    assert store.export_snapshot() == before


def test_c5_contract_rejects_privacy_scope_without_any_write() -> None:
    store = GameplayEventStore()
    contract = FixedBaseBranchReplayContract.from_preview_inputs(
        branch_ref="branch:c5",
        base_event_digest="sha256:empty",
        base_checkpoint_sequence=0,
        tail_boundary=0,
        calibration_ref="calibration:c5",
        calibration=_calibration().model_dump(mode="json"),
        source_digests={},
        candidate_digests=(),
        family_digests=(),
        dataset_digest="sha256:dataset-c5",
        privacy_scope="creator_debug",
    )
    before = store.export_snapshot()

    error = contract.validate_branch_stream(
        stream_id="gameplay:branch_preview:branch:c5",
        branch_ref="branch:c5",
        privacy_scope="project",
    )

    assert error == "branch_replay_privacy_mismatch"
    assert store.export_snapshot() == before


def test_c5_durable_projection_exposes_stable_contract_projection_digest() -> None:
    store = GameplayEventStore()
    authority = _authority(store)
    assert authority.preview(
        request=_request(),
        dataset=_dataset(),
        calibration=_calibration(),
        family_inputs=(),
        candidates=(_candidate(intent_ref="intent:c5:a", priority=1), _candidate(intent_ref="intent:c5:b", priority=2)),
        mode=_mode(),
    ).accepted
    assert authority.record_isolated_branch_snapshot(
        branch_ref="branch:c5",
        expected_revision=0,
        idempotency_key="snapshot:c5",
        privacy_scope="creator_debug",
    ).committed

    fresh = _authority(store)
    full = fresh.durable_branch_projection("branch:c5")
    tail = fresh.durable_branch_projection("branch:c5", checkpoint_at=3)

    assert full["replay_contract_digest"] == tail["replay_contract_digest"]
    assert full["projection_hash"] == tail["projection_hash"]
    assert full["projection_hash"] == full["replay_contract_projection_digest"]


def test_c5_fixed_supply_promotion_admission_reads_matching_replay_contract() -> None:
    store = GameplayEventStore()
    organization = OrganizationAuthority(store=store)
    assert organization.grant_commerce_budget(
        command_id="command:c5:grant",
        organization_ref="organization:bakery",
        grant_ref="grant:c5",
        budget_reservation_ref="reservation:c5",
        amount_minor=100,
        policy_revision="policy:c5",
        idempotency_key="idempotency:c5:grant",
        causation_id="cause:c5:grant",
        correlation_id="corr:c5:grant",
    ).committed
    authority = _authority(store)
    candidate = BatchIntentCandidate(
        intent_ref="intent:c5:supply",
        profile_ref="character:char_a",
        intent_kind="supply",
        payload={
            "organization_ref": "organization:bakery",
            "counterparty_organization_ref": "organization:supplier",
            "commitment_ref": "commitment:c5",
            "organization_grant_refs": ("grant:c5",),
            "budget_reservation_refs": ("reservation:c5",),
        },
        expected_revisions={"gameplay:organization:organization:bakery": 1},
        priority=1,
        policy_revision="policy:c5",
        package_revision="package:c5",
        idempotency_key="intent:c5:supply",
        correlation_id="corr:intent:c5:supply",
        source_ref="planner",
        privacy_scope="actor:self",
    )
    branch_ref = "branch:c5:supply"
    assert authority.preview(
        request=_request(branch_ref=branch_ref),
        dataset=_dataset(),
        calibration=_calibration(),
        family_inputs=(),
        candidates=(candidate,),
        mode=_mode(),
    ).accepted
    assert authority.settle_accepted_supply_scenario(
        branch_ref=branch_ref,
        intent_ref=candidate.intent_ref,
    ).committed
    admission_event = store.read_stream(authority.admission_stream_id(branch_ref=branch_ref))[0]

    validated = organization._branch_supply_admission_payload_for(
        admission_event_id=admission_event.event_id,
    )

    assert validated["replay_contract_digest"] == validated["replay_contract"].contract_digest
    assert validated["replay_contract"].branch_ref == branch_ref


def test_c5_unregistered_promotion_remains_zero_write() -> None:
    store = GameplayEventStore()
    before = store.export_snapshot()

    result = BranchPreviewAuthority.promote("branch:c5:unregistered")

    assert result.accepted is False
    assert result.error_code == "branch_promotion_unsupported"
    assert store.export_snapshot() == before
