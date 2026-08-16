from __future__ import annotations

from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.settlement_plan import SettlementPlan
from app.gameplay.shared_contracts import GameplayCommandEnvelope
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
        revision="mode:inf4j:1",
        cadence_class="daily",
        batch_limit=1,
        wake_budget=1,
        catch_up_limit=1,
        allowed_intent_kinds=("inspection",),
        degraded_threshold=1,
    )


def _candidate(*, passed: bool = False) -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref="intent:branch:government:failed-inspection",
        profile_ref="character:char_a",
        intent_kind="inspection",
        payload={
            "organization_ref": "organization:bakery",
            "inspection_ref": "inspection:branch:government:failed",
            "jurisdiction_ref": "jurisdiction:bakery",
            "policy_digest": "sha256:policy:government:failed",
            "evidence_ref": "evidence:branch:government:failed",
            "passed": passed,
        },
        priority=1,
        policy_revision="mode:inf4j:1",
        package_revision="package:inf4j:1",
        idempotency_key="intent:branch:government:failed-inspection",
        correlation_id="corr:branch:government:failed-inspection",
        source_ref="planner",
        privacy_scope="actor:self",
        expected_revisions={"gameplay:government:organization:bakery": 0},
    )


def _preview(
    authority: BranchPreviewAuthority,
    *,
    branch_ref: str,
    candidate: BatchIntentCandidate,
) -> None:
    assert authority.preview(
        request=BranchPreviewRequest(
            branch_ref=branch_ref,
            world_ref="world:bakery",
            base_event_digest="sha256:empty",
            deterministic_seed="seed:government:remediation:1",
            active_revision_refs=("mode:inf4j:1",),
            calibration_ref="calibration:inf4j:1",
            privacy_scope="creator_debug",
        ),
        dataset=ReferenceDataset(
            dataset_ref="dataset:government:remediation",
            provenance="fixture",
            license_ref="license:permitted",
            schema_revision="1",
            digest="sha256:dataset:government:remediation",
            classification="creator_debug",
            allowed_scopes=("creator_debug",),
        ),
        calibration=CalibrationInput(
            calibration_ref="calibration:inf4j:1",
            dataset_ref="dataset:government:remediation",
            parameter_mapping_revision="map:inf4j:1",
            world_revision="world:inf4j:1",
            ruleset_revision="rules:inf4j:1",
            privacy_scope="creator_debug",
        ),
        family_inputs=(),
        candidates=(candidate,),
        mode=_mode(),
    ).accepted


def _authority(*, candidate: BatchIntentCandidate | None = None) -> tuple[GameplayEventStore, BranchPreviewAuthority]:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(
        store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR),
    )
    _preview(
        authority,
        branch_ref="branch:government:remediation:1",
        candidate=candidate or _candidate(),
    )
    return store, authority


def _append_forged_cross_branch_admission(store: GameplayEventStore) -> str:
    command = GameplayCommandEnvelope(
        command_id="command:forged:cross-branch:failed",
        command_type="gameplay.branch_preview.record_inspection_admission",
        command_version=1,
        principal_ref="authority:branch_preview",
        actor_ref=None,
        project_ref=None,
        transaction_id="transaction:forged:cross-branch:failed",
        idempotency_key="idempotency:forged:cross-branch:failed",
        expected_revisions={"gameplay:branch_preview:branch:government:wrong": 0},
        read_set_revisions={"gameplay:government:organization:bakery": 0},
        causation_id="sha256:forged-candidate",
        correlation_id="correlation:forged:cross-branch:failed",
        source_ref="authority:branch_preview",
        submitted_at="branch-scenario",
        pinned_revisions={"government_source": 0},
        payload={
            "stream_ref": "gameplay:branch_preview:branch:government:wrong",
            "event_type": "gameplay.branch_preview.inspection_admission_recorded",
            "visibility_policy": "creator_debug",
            "branch_ref": "branch:government:target",
            "intent_ref": "intent:forged:cross-branch:failed",
            "base_event_digest": "sha256:forged-base",
            "candidate_digest": "sha256:forged-candidate",
            "fragment_digest": "sha256:forged-fragment",
            "organization_ref": "organization:bakery",
            "inspection_ref": "inspection:forged:cross-branch:failed",
            "jurisdiction_ref": "jurisdiction:bakery",
            "policy_revision": "policy:forged",
            "policy_digest": "sha256:forged-policy",
            "evidence_ref": "evidence:forged",
            "passed": False,
            "source_stream": "gameplay:government:organization:bakery",
            "source_government_revision": 0,
        },
    )
    result = store.append_batch(SettlementPlan.from_command_envelope(command).to_atomic_event_batch())
    assert result.committed and len(result.committed_event_ids) == 1
    return result.committed_event_ids[0]


def test_failed_inspection_settles_fixed_government_remediation_on_scenario_stream() -> None:
    store, authority = _authority()
    settle = getattr(authority, "settle_accepted_failed_inspection_remediation_scenario", None)

    assert settle is not None
    receipt = settle(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    stream = "gameplay:government_branch:branch:government:remediation:1:organization:bakery"
    assert receipt.committed
    assert store.get_stream_head(stream) == 1
    assert store.get_stream_head("gameplay:government:organization:bakery") == 0
    event = store.read_stream(stream)[0]
    assert event.event_type == "gameplay.government.branch_inspection_remediation_recorded"
    assert event.payload["remediation_ref"] == "branch-remediation:branch:government:remediation:1:inspection:branch:government:failed"
    assert event.payload["remediation_action"] == "follow_up_required"


def test_failed_inspection_remediation_derives_row_from_durable_preview_admission() -> None:
    store, authority = _authority()

    receipt = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    admission = store.read_stream("gameplay:branch_preview:branch:government:remediation:1")[0]
    scenario = store.read_stream(
        "gameplay:government_branch:branch:government:remediation:1:organization:bakery"
    )[0]
    assert receipt.committed
    assert admission.event_type == "gameplay.branch_preview.inspection_admission_recorded"
    assert admission.payload["passed"] is False
    assert scenario.payload["admission_event_id"] == admission.event_id


def test_direct_forged_government_remediation_submission_is_zero_write() -> None:
    store = GameplayEventStore()

    with __import__("pytest").raises(TypeError):
        GovernmentAuthority(store=store).settle_branch_inspection_remediation(
            branch_ref="branch:forged:remediation",
            base_event_digest="sha256:forged-base",
            candidate_digest="sha256:forged-candidate",
            organization_ref="organization:bakery",
            inspection_ref="inspection:forged",
            jurisdiction_ref="jurisdiction:bakery",
            policy_revision="policy:forged",
            policy_digest="sha256:forged-policy",
            evidence_ref="evidence:forged",
            source_government_revision=0,
            expected_revision=0,
            idempotency_key="idempotency:forged-remediation",
            correlation_id="correlation:forged-remediation",
            privacy_scope="creator_debug",
        )

    assert store.read_events() == []


def test_failed_inspection_remediation_rejects_cross_branch_preview_stream_without_append() -> None:
    store = GameplayEventStore()
    admission_event_id = _append_forged_cross_branch_admission(store)
    before = len(store.read_events())

    with pytest.raises(ValueError, match="branch_scenario_admission_invalid"):
        GovernmentAuthority(store=store).settle_branch_inspection_remediation(
            admission_event_id=admission_event_id,
            expected_revision=0,
            idempotency_key="government:forged-cross-branch-remediation",
            correlation_id="government:forged-cross-branch-remediation",
            privacy_scope="creator_debug",
        )

    assert len(store.read_events()) == before
    assert store.get_stream_head(
        "gameplay:government_branch:branch:government:target:organization:bakery"
    ) == 0


def test_failed_inspection_remediation_duplicate_replays_without_second_append() -> None:
    store, authority = _authority()
    first = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )
    duplicate = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.get_stream_head("gameplay:government_branch:branch:government:remediation:1:organization:bakery") == 1


def test_failed_inspection_remediation_derives_fixed_identity_and_action() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    ).committed

    payload = store.read_stream(
        "gameplay:government_branch:branch:government:remediation:1:organization:bakery"
    )[0].payload

    assert payload["remediation_ref"] == "branch-remediation:branch:government:remediation:1:inspection:branch:government:failed"
    assert payload["remediation_action"] == "follow_up_required"


def test_failed_inspection_remediation_rejects_public_scope_without_append() -> None:
    store, authority = _authority()

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
        privacy_scope="public",
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "branch_scenario_privacy_denied"
    assert store.read_events() == []


def test_failed_inspection_remediation_rejects_unknown_candidate_without_append() -> None:
    store, authority = _authority()

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:missing",
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "branch_scenario_candidate_unavailable"
    assert store.read_events() == []


def test_failed_inspection_remediation_rejects_passed_candidate_without_append() -> None:
    store, authority = _authority(candidate=_candidate(passed=True))

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "branch_scenario_inspection_must_fail"
    assert store.read_events() == []


def test_failed_inspection_remediation_rejects_non_boolean_passed_without_append() -> None:
    store, authority = _authority(candidate=_candidate(passed=""))  # type: ignore[arg-type]

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "branch_scenario_candidate_unavailable"
    assert store.read_events() == []


def test_failed_inspection_remediation_rejects_stale_scenario_revision_without_append() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    ).committed

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
        idempotency_key="branch-remediation:stale",
        expected_revision=0,
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "revision_conflict"
    assert store.get_stream_head("gameplay:government_branch:branch:government:remediation:1:organization:bakery") == 1


def test_failed_inspection_remediation_rejects_stale_government_source_without_append() -> None:
    store, authority = _authority()
    assert GovernmentAuthority(store=store).settle_tax_assessment(
        organization_ref="organization:bakery",
        period_ref="period:inf4j:source-advance",
        revenue=10.0,
        rate=0.1,
        policy_revision="policy:inf4j:source-advance",
        command_id="command:inf4j:source-advance",
        idempotency_key="idem:inf4j:source-advance",
        causation_id="cause:inf4j:source-advance",
        correlation_id="corr:inf4j:source-advance",
    ).committed

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "revision_conflict"
    assert store.get_stream_head("gameplay:government_branch:branch:government:remediation:1:organization:bakery") == 0


def test_failed_inspection_remediation_rejects_changed_duplicate_without_append() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
        idempotency_key="branch-remediation:shared",
    ).committed
    _preview(
        authority,
        branch_ref="branch:government:remediation:2",
        candidate=_candidate(),
    )

    rejected = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:2",
        intent_ref="intent:branch:government:failed-inspection",
        idempotency_key="branch-remediation:shared",
    )

    assert not rejected.committed
    assert rejected.failure and rejected.failure.error_code == "idempotency_key_reused"
    assert store.get_stream_head("gameplay:government_branch:branch:government:remediation:2:organization:bakery") == 0


def test_failed_inspection_remediation_projection_replays_checkpoint_tail() -> None:
    _, authority = _authority()
    assert authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    ).committed

    full = authority.government_branch_scenario_projection(
        "branch:government:remediation:1", organization_ref="organization:bakery"
    )
    tail = authority.government_branch_scenario_projection(
        "branch:government:remediation:1",
        organization_ref="organization:bakery",
        checkpoint_at=0,
    )

    assert full["remediation_refs"] == (
        "branch-remediation:branch:government:remediation:1:inspection:branch:government:failed",
    )
    assert full["projection_hash"] == tail["projection_hash"]


def test_failed_inspection_remediation_outbox_is_creator_debug_scoped() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    ).committed

    entries = store.list_outbox()
    assert len(entries) == 2
    assert {entry.audience for entry in entries} == {"creator_debug"}
    assert {entry.topic for entry in entries} == {
        "world.branch_preview.inspection_admission",
        "world.government_branch.scenario_projection",
    }


def test_failed_inspection_remediation_receipt_rebuilds_from_durable_event() -> None:
    store, authority = _authority()
    append = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )
    receipt_for = getattr(GovernmentAuthority(store=store), "branch_remediation_receipt_for", None)

    assert append.committed and receipt_for is not None
    receipt = receipt_for(event_id=append.committed_event_ids[0], privacy_scope="creator_debug")
    assert receipt.transaction_id == append.transaction_id
    assert receipt.committed_event_ids == tuple(append.committed_event_ids)
    assert receipt.scenario_stream == "gameplay:government_branch:branch:government:remediation:1:organization:bakery"
    assert receipt.projection_hash == authority.government_branch_scenario_projection(
        "branch:government:remediation:1", organization_ref="organization:bakery"
    )["projection_hash"]


def test_failed_inspection_remediation_receipt_rejects_non_remediation_event_without_write() -> None:
    store, authority = _authority()
    append = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )
    before = len(store.read_events())

    with __import__("pytest").raises(ValueError, match="branch_remediation_receipt_event_invalid"):
        GovernmentAuthority(store=store).branch_remediation_receipt_for(
            event_id="event:missing", privacy_scope="creator_debug"
        )

    assert append.committed
    assert len(store.read_events()) == before


def test_failed_inspection_remediation_receipt_duplicate_append_rebuilds_stably() -> None:
    store, authority = _authority()
    first = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )
    duplicate = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )

    receipt_for = GovernmentAuthority(store=store).branch_remediation_receipt_for
    first_receipt = receipt_for(event_id=first.committed_event_ids[0], privacy_scope="creator_debug")
    duplicate_receipt = receipt_for(event_id=duplicate.committed_event_ids[0], privacy_scope="creator_debug")

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert first_receipt == duplicate_receipt
    assert len(store.read_events()) == 2


def test_failed_inspection_remediation_receipt_rejects_noncreator_scope_without_write() -> None:
    store, authority = _authority()
    append = authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    )
    before = len(store.read_events())

    with __import__("pytest").raises(ValueError, match="branch_remediation_receipt_privacy_denied"):
        GovernmentAuthority(store=store).branch_remediation_receipt_for(
            event_id=append.committed_event_ids[0], privacy_scope="public"
        )

    assert len(store.read_events()) == before


def test_failed_inspection_remediation_keeps_production_replay_and_promotion_zero_write() -> None:
    store, authority = _authority()
    production_before = authority.production_replay().projection_hash
    assert authority.settle_accepted_failed_inspection_remediation_scenario(
        branch_ref="branch:government:remediation:1",
        intent_ref="intent:branch:government:failed-inspection",
    ).committed
    before_promotion = len(store.read_events())

    promotion = authority.promote("branch:government:remediation:1")

    assert authority.production_replay().projection_hash == production_before
    assert not promotion.accepted and promotion.error_code == "branch_promotion_unsupported"
    assert len(store.read_events()) == before_promotion
