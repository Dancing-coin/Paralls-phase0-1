from __future__ import annotations

from app.gameplay.action_consequence_runtime import ActionConsequenceBoundary, ActionConsequenceIntent, WorldDeathConfirmationIntent
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.investigation_conflict import InvestigationConflictAuthority
from app.gameplay.settlement_plan import build_atomic_event_batch
from test_p5_investigation_conflict import _registry
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def test_missing_consequence_source_and_evidence_are_zero_write() -> None:
    store = GameplayEventStore()
    boundary = ActionConsequenceBoundary(store)
    missing_evidence = boundary.validate(
        ActionConsequenceIntent(
            source_event_id="event:missing",
            source_event_type="gameplay.conflict.terminal_outcome_recorded",
            target_actor_ref="character:survivor",
            owner_kind="body",
            expected_source_revision=1,
            policy_revision="policy:action@1",
            evidence_refs=(),
        )
    )
    assert not missing_evidence.accepted
    assert missing_evidence.error_code == "action_consequence_evidence_missing"
    assert store.read_events() == []


def test_world_death_requires_explicit_case_death_source() -> None:
    store = GameplayEventStore()
    boundary = ActionConsequenceBoundary(store)
    result = boundary.validate_world_death(
        WorldDeathConfirmationIntent(
            source_event_id="event:missing",
            target_actor_ref="character:survivor",
            expected_source_revision=1,
            confirmation_ref="confirmation:1",
            confirmed=True,
            policy_revision="policy:death@1",
        )
    )
    assert not result.accepted
    assert result.error_code == "world_death_source_missing"
    assert store.read_events() == []


def test_wrong_owner_fragment_is_zero_write() -> None:
    store = GameplayEventStore()
    boundary = ActionConsequenceBoundary(store)
    result = boundary.validate(
        ActionConsequenceIntent(
            source_event_id="event:missing",
            source_event_type="gameplay.conflict.terminal_outcome_recorded",
            target_actor_ref="character:survivor",
            owner_kind="body",
            owner_principal_ref="authority:inventory",
            expected_source_revision=1,
            policy_revision="policy:action@1",
            evidence_refs=("evidence:1",),
        )
    )
    assert not result.accepted
    assert result.error_code == "action_consequence_owner_fragment_invalid"
    assert store.read_events() == []


def test_explicit_world_death_confirmation_is_owner_appended() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(
        build_atomic_event_batch(
            command_id="case-death",
            principal_ref="authority:p5:investigation-conflict",
            stream_id=source_stream,
            expected_revision=0,
            event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
            idempotency_key="case-death",
            causation_id="case",
            correlation_id="case",
        )
    )
    source_event = store.get_event(source.committed_event_ids[0])
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    command = GameplayCommandEnvelope(
        command_id="death-confirm",
        command_type="gameplay.conflict.confirm_world_death",
        command_version=1,
        principal_ref="authority:p5:investigation-conflict",
        actor_ref="character:survivor",
        project_ref="project:case",
        transaction_id="transaction:death-confirm",
        idempotency_key="death-confirm",
        expected_revisions={source_stream: 1},
        causation_id="case-death",
        correlation_id="case",
        source_ref=source_event.event_id,
        submitted_at="now",
    )
    result = authority.confirm_world_death(
        command=command,
        intent=WorldDeathConfirmationIntent(
            source_event_id=source_event.event_id,
            target_actor_ref="character:survivor",
            expected_source_revision=1,
            confirmation_ref="confirmation:case:1",
            confirmed=True,
            policy_revision="policy:death@1",
        ),
    )
    assert result.committed
    assert store.read_events()[-1].event_type == "gameplay.conflict.world_death_commit_confirmed"
