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
        revision="mode:1",
        cadence_class="daily",
        batch_limit=3,
        wake_budget=3,
        catch_up_limit=2,
        allowed_intent_kinds=("inspection",),
        degraded_threshold=1,
    )


def _request(branch_ref: str = "branch:government:1") -> BranchPreviewRequest:
    return BranchPreviewRequest(
        branch_ref=branch_ref,
        world_ref="world:bakery",
        base_event_digest="sha256:empty",
        deterministic_seed="seed:government:1",
        active_revision_refs=("mode:1",),
        calibration_ref="calibration:1",
        privacy_scope="creator_debug",
    )


def _dataset() -> ReferenceDataset:
    return ReferenceDataset(
        dataset_ref="dataset:prices:government",
        provenance="fixture",
        license_ref="license:permitted",
        schema_revision="1",
        digest="sha256:dataset:government",
        classification="creator_debug",
        allowed_scopes=("creator_debug",),
    )


def _calibration() -> CalibrationInput:
    return CalibrationInput(
        calibration_ref="calibration:1",
        dataset_ref="dataset:prices:government",
        parameter_mapping_revision="map:1",
        world_revision="world:1",
        ruleset_revision="rules:1",
        privacy_scope="creator_debug",
    )


def _inspection() -> BatchIntentCandidate:
    return BatchIntentCandidate(
        intent_ref="intent:branch:government:inspection",
        profile_ref="character:char_a",
        intent_kind="inspection",
        payload={
            "organization_ref": "organization:bakery",
            "inspection_ref": "inspection:branch:government",
            "jurisdiction_ref": "jurisdiction:bakery",
            "policy_digest": "sha256:policy:government",
            "evidence_ref": "evidence:branch:government",
            "passed": True,
        },
        priority=1,
        policy_revision="mode:1",
        package_revision="package:1",
        idempotency_key="intent:branch:government:inspection",
        correlation_id="corr:branch:government:inspection",
        source_ref="planner",
        privacy_scope="actor:self",
        expected_revisions={"gameplay:government:organization:bakery": 0},
    )


def _authority() -> tuple[GameplayEventStore, BranchPreviewAuthority]:
    store = GameplayEventStore()
    authority = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    assert authority.preview(
        request=_request(), dataset=_dataset(), calibration=_calibration(), family_inputs=(), candidates=(_inspection(),), mode=_mode()
    ).accepted
    return store, authority


def _append_forged_cross_branch_admission(store: GameplayEventStore) -> str:
    command = GameplayCommandEnvelope(
        command_id="command:forged:cross-branch:passed",
        command_type="gameplay.branch_preview.record_inspection_admission",
        command_version=1,
        principal_ref="authority:branch_preview",
        actor_ref=None,
        project_ref=None,
        transaction_id="transaction:forged:cross-branch:passed",
        idempotency_key="idempotency:forged:cross-branch:passed",
        expected_revisions={"gameplay:branch_preview:branch:government:wrong": 0},
        read_set_revisions={"gameplay:government:organization:bakery": 0},
        causation_id="sha256:forged-candidate",
        correlation_id="correlation:forged:cross-branch:passed",
        source_ref="authority:branch_preview",
        submitted_at="branch-scenario",
        pinned_revisions={"government_source": 0},
        payload={
            "stream_ref": "gameplay:branch_preview:branch:government:wrong",
            "event_type": "gameplay.branch_preview.inspection_admission_recorded",
            "visibility_policy": "creator_debug",
            "branch_ref": "branch:government:target",
            "intent_ref": "intent:forged:cross-branch:passed",
            "base_event_digest": "sha256:forged-base",
            "candidate_digest": "sha256:forged-candidate",
            "fragment_digest": "sha256:forged-fragment",
            "organization_ref": "organization:bakery",
            "inspection_ref": "inspection:forged:cross-branch:passed",
            "jurisdiction_ref": "jurisdiction:bakery",
            "policy_revision": "policy:forged",
            "policy_digest": "sha256:forged-policy",
            "evidence_ref": "evidence:forged",
            "passed": True,
            "source_stream": "gameplay:government:organization:bakery",
            "source_government_revision": 0,
        },
    )
    result = store.append_batch(SettlementPlan.from_command_envelope(command).to_atomic_event_batch())
    assert result.committed and len(result.committed_event_ids) == 1
    return result.committed_event_ids[0]


def test_accepted_inspection_branch_proposal_settles_on_government_scenario_stream() -> None:
    store, authority = _authority()
    receipt = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection")
    assert receipt.committed
    assert store.get_stream_head("gameplay:government_branch:branch:government:1:organization:bakery") == 1
    assert store.get_stream_head("gameplay:government:organization:bakery") == 0
    assert authority.government_branch_scenario_projection("branch:government:1", organization_ref="organization:bakery")["inspection_refs"] == ("inspection:branch:government",)


def test_government_branch_scenario_derives_passed_row_from_durable_preview_admission() -> None:
    store, authority = _authority()

    receipt = authority.settle_accepted_inspection_scenario(
        branch_ref="branch:government:1",
        intent_ref="intent:branch:government:inspection",
    )

    admission_stream = "gameplay:branch_preview:branch:government:1"
    assert receipt.committed
    assert store.get_stream_head(admission_stream) == 1
    admission = store.read_stream(admission_stream)[0]
    assert admission.event_type == "gameplay.branch_preview.inspection_admission_recorded"
    assert admission.payload["passed"] is True
    assert admission.payload["candidate_digest"] == store.read_stream(
        "gameplay:government_branch:branch:government:1:organization:bakery"
    )[0].payload["candidate_digest"]


def test_government_branch_scenario_rejects_missing_durable_preview_admission_without_append() -> None:
    store = GameplayEventStore()

    with __import__("pytest").raises(ValueError, match="branch_scenario_admission_missing"):
        GovernmentAuthority(store=store).settle_branch_inspection(
            admission_event_id="event:missing",
            expected_revision=0,
            idempotency_key="government:forged",
            correlation_id="government:forged",
            privacy_scope="creator_debug",
        )

    assert store.read_events() == []


def test_government_branch_scenario_rejects_cross_branch_preview_stream_without_append() -> None:
    store = GameplayEventStore()
    admission_event_id = _append_forged_cross_branch_admission(store)
    before = len(store.read_events())

    with pytest.raises(ValueError, match="branch_scenario_admission_invalid"):
        GovernmentAuthority(store=store).settle_branch_inspection(
            admission_event_id=admission_event_id,
            expected_revision=0,
            idempotency_key="government:forged-cross-branch",
            correlation_id="government:forged-cross-branch",
            privacy_scope="creator_debug",
        )

    assert len(store.read_events()) == before
    assert store.get_stream_head(
        "gameplay:government_branch:branch:government:target:organization:bakery"
    ) == 0


def test_government_branch_scenario_duplicate_idempotency_replays_without_second_append() -> None:
    store, authority = _authority()
    first = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection")
    duplicate = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection")
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.get_stream_head("gameplay:government_branch:branch:government:1:organization:bakery") == 1


def test_government_branch_scenario_duplicate_retry_replays_after_production_source_advances() -> None:
    store, authority = _authority()
    first = authority.settle_accepted_inspection_scenario(
        branch_ref="branch:government:1",
        intent_ref="intent:branch:government:inspection",
        idempotency_key="government:retry-after-source-advance",
    )
    advance = GovernmentAuthority(store=store).settle_tax_assessment(
        organization_ref="organization:bakery",
        period_ref="period:retry-after-source-advance",
        revenue=10.0,
        rate=0.1,
        policy_revision="policy:retry-after-source-advance",
        command_id="command:government:retry-after-source-advance",
        idempotency_key="idem:government:retry-after-source-advance",
        causation_id="cause:government:retry-after-source-advance",
        correlation_id="corr:government:retry-after-source-advance",
    )
    duplicate = authority.settle_accepted_inspection_scenario(
        branch_ref="branch:government:1",
        intent_ref="intent:branch:government:inspection",
        idempotency_key="government:retry-after-source-advance",
    )

    assert first.committed and advance.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert store.get_stream_head("gameplay:government_branch:branch:government:1:organization:bakery") == 1
    assert store.get_stream_head("gameplay:government:organization:bakery") == 1


def test_government_branch_scenario_changed_duplicate_rejects_without_append() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection", idempotency_key="government:shared").committed
    assert authority.preview(request=_request("branch:government:2"), dataset=_dataset(), calibration=_calibration(), family_inputs=(), candidates=(_inspection(),), mode=_mode()).accepted
    rejected = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:2", intent_ref="intent:branch:government:inspection", idempotency_key="government:shared")
    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "idempotency_key_reused"
    assert store.get_stream_head("gameplay:government_branch:branch:government:1:organization:bakery") == 1
    assert store.get_stream_head("gameplay:government_branch:branch:government:2:organization:bakery") == 0


def test_government_branch_scenario_rejects_privacy_without_append() -> None:
    store, authority = _authority()
    rejected = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection", privacy_scope="public")
    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "branch_scenario_privacy_denied"
    assert store.read_events() == []


def test_government_branch_scenario_rejects_unknown_candidate_without_append() -> None:
    store, authority = _authority()
    rejected = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="missing")
    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "branch_scenario_candidate_unavailable"
    assert store.read_events() == []


def test_government_branch_scenario_rejects_failed_inspection_without_append() -> None:
    store, authority = _authority()
    candidate = _inspection().model_copy(update={"payload": {**_inspection().payload, "passed": False}})
    failed = BranchPreviewAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILE_DIR))
    assert failed.preview(request=_request("branch:government:failed"), dataset=_dataset(), calibration=_calibration(), family_inputs=(), candidates=(candidate,), mode=_mode()).accepted
    rejected = failed.settle_accepted_inspection_scenario(branch_ref="branch:government:failed", intent_ref="intent:branch:government:inspection")
    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "branch_scenario_inspection_must_pass"
    assert store.read_events() == []


def test_government_branch_scenario_rejects_stale_revision_without_append() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection").committed
    rejected = authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection", idempotency_key="government:stale", expected_revision=0)
    assert not rejected.committed and rejected.failure and rejected.failure.error_code == "revision_conflict"
    assert store.get_stream_head("gameplay:government_branch:branch:government:1:organization:bakery") == 1


def test_government_branch_scenario_checkpoint_tail_replay_matches_full() -> None:
    _, authority = _authority()
    assert authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection").committed
    full = authority.government_branch_scenario_projection("branch:government:1", organization_ref="organization:bakery")
    tail = authority.government_branch_scenario_projection("branch:government:1", organization_ref="organization:bakery", checkpoint_at=0)
    assert full["projection_hash"] == tail["projection_hash"]


def test_government_branch_scenario_does_not_change_production_replay() -> None:
    _, authority = _authority()
    production_before = authority.production_replay().projection_hash
    assert authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection").committed
    assert authority.production_replay().projection_hash == production_before


def test_government_branch_scenario_promotion_remains_unsupported() -> None:
    _, authority = _authority()
    assert authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection").committed
    promotion = authority.promote("branch:government:1")
    assert promotion.accepted is False and promotion.error_code == "branch_promotion_unsupported"


def test_government_branch_scenario_emits_only_scoped_scenario_outbox() -> None:
    store, authority = _authority()
    assert authority.settle_accepted_inspection_scenario(branch_ref="branch:government:1", intent_ref="intent:branch:government:inspection").committed
    assert any(entry.topic == "world.government_branch.scenario_projection" and entry.audience == "creator_debug" for entry in store.list_outbox())
