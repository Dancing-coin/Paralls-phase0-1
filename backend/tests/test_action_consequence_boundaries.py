from __future__ import annotations

import pytest
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import ProjectionCheckpoint
from app.gameplay.p5.contracts import canonical_sha256_digest
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry

from app.gameplay.action_consequence_runtime import ActionConsequenceBoundary, ActionConsequenceIntent, WorldDeathConfirmationIntent
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


@pytest.mark.parametrize(
    "command_change",
    [
        {"principal_ref": "authority:forged"},
        {"command_type": "gameplay.unrelated.write"},
    ],
)
def test_world_death_rejects_untrusted_command_boundary_zero_write(command_change) -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(build_atomic_event_batch(
        command_id="case-death", principal_ref="authority:p5:investigation-conflict",
        stream_id=source_stream, expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
        idempotency_key="case-death", causation_id="case", correlation_id="case",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    command = GameplayCommandEnvelope(
        command_id="death-confirm", command_type="gameplay.conflict.confirm_world_death", command_version=1,
        principal_ref="authority:p5:investigation-conflict", actor_ref="character:survivor", project_ref="project:case",
        transaction_id="transaction:death-confirm", idempotency_key="death-confirm", expected_revisions={source_stream: 1},
        causation_id="case-death", correlation_id="case", source_ref=source_event.event_id, submitted_at="now",
    ).model_copy(update=command_change)
    intent = WorldDeathConfirmationIntent(
        source_event_id=source_event.event_id, target_actor_ref="character:survivor", expected_source_revision=1,
        confirmation_ref="confirmation:case:1", confirmed=True, policy_revision="policy:death@1",
    )

    result = InvestigationConflictAuthority(registry=_registry(), store=store).confirm_world_death(
        command=command, intent=intent,
    )

    assert not result.committed
    assert result.error_code == "world_death_command_boundary_invalid"
    assert store.get_stream_head(source_stream) == 1


def test_explicit_world_death_confirmation_commits_on_guarded_stormnight_store() -> None:
    store = GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(build_atomic_event_batch(
        command_id="case-death", principal_ref="authority:p5:investigation-conflict",
        stream_id=source_stream, expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
        idempotency_key="case-death", causation_id="case", correlation_id="case",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    command = GameplayCommandEnvelope(
        command_id="death-confirm-guarded", command_type="gameplay.conflict.confirm_world_death", command_version=1,
        principal_ref="authority:p5:investigation-conflict", actor_ref="character:survivor", project_ref="project:case",
        transaction_id="transaction:death-confirm-guarded", idempotency_key="death-confirm-guarded", expected_revisions={source_stream: 1},
        causation_id="case-death", correlation_id="case", source_ref=source_event.event_id, submitted_at="now",
    )
    result = InvestigationConflictAuthority(registry=_registry(), store=store).confirm_world_death(
        command=command,
        intent=WorldDeathConfirmationIntent(
            source_event_id=source_event.event_id, target_actor_ref="character:survivor", expected_source_revision=1,
            confirmation_ref="confirmation:case:guarded", confirmed=True, policy_revision="policy:death@1",
        ),
    )
    assert result.committed


def test_world_death_confirmation_retry_recovers_receipt_after_lost_response(monkeypatch) -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(build_atomic_event_batch(
        command_id="case-death", principal_ref="authority:p5:investigation-conflict",
        stream_id=source_stream, expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
        idempotency_key="case-death", causation_id="case", correlation_id="case",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    command = GameplayCommandEnvelope(
        command_id="death-confirm", command_type="gameplay.conflict.confirm_world_death", command_version=1,
        principal_ref="authority:p5:investigation-conflict", actor_ref="character:survivor", project_ref="project:case",
        transaction_id="transaction:death-confirm", idempotency_key="death-confirm", expected_revisions={source_stream: 1},
        causation_id="case-death", correlation_id="case", source_ref=source_event.event_id, submitted_at="now",
    )
    intent = WorldDeathConfirmationIntent(
        source_event_id=source_event.event_id, target_actor_ref="character:survivor", expected_source_revision=1,
        confirmation_ref="confirmation:case:1", confirmed=True, policy_revision="policy:death@1",
    )
    append = store.append_batch
    def append_then_lose_response(batch):
        append(batch)
        raise TimeoutError("response lost after commit")
    monkeypatch.setattr(store, "append_batch", append_then_lose_response)
    with pytest.raises(TimeoutError, match="response lost"):
        authority.confirm_world_death(command=command, intent=intent)
    monkeypatch.setattr(store, "append_batch", append)

    retry = authority.confirm_world_death(command=command, intent=intent)

    assert retry.committed
    assert retry.idempotency_status == "duplicate_replayed"
    assert len([event for event in store.read_events() if event.event_type == "gameplay.conflict.world_death_commit_confirmed"]) == 1


def test_world_death_confirmation_changed_duplicate_is_rejected() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(build_atomic_event_batch(
        command_id="case-death", principal_ref="authority:p5:investigation-conflict",
        stream_id=source_stream, expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
        idempotency_key="case-death", causation_id="case", correlation_id="case",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    command = GameplayCommandEnvelope(
        command_id="death-confirm", command_type="gameplay.conflict.confirm_world_death", command_version=1,
        principal_ref="authority:p5:investigation-conflict", actor_ref="character:survivor", project_ref="project:case",
        transaction_id="transaction:death-confirm", idempotency_key="death-confirm", expected_revisions={source_stream: 1},
        causation_id="case-death", correlation_id="case", source_ref=source_event.event_id, submitted_at="now",
    )
    intent = WorldDeathConfirmationIntent(
        source_event_id=source_event.event_id, target_actor_ref="character:survivor", expected_source_revision=1,
        confirmation_ref="confirmation:case:1", confirmed=True, policy_revision="policy:death@1",
    )
    assert authority.confirm_world_death(command=command, intent=intent).committed
    changed = authority.confirm_world_death(
        command=command, intent=intent.model_copy(update={"confirmed": False})
    )
    assert not changed.committed
    assert changed.error_code == "world_death_idempotency_reused"


def test_world_death_confirmation_changed_command_identity_is_rejected() -> None:
    store = GameplayEventStore()
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(build_atomic_event_batch(
        command_id="case-death", principal_ref="authority:p5:investigation-conflict",
        stream_id=source_stream, expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
        idempotency_key="case-death", causation_id="case", correlation_id="case",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    command = GameplayCommandEnvelope(
        command_id="death-confirm", command_type="gameplay.conflict.confirm_world_death", command_version=1,
        principal_ref="authority:p5:investigation-conflict", actor_ref="character:survivor", project_ref="project:case",
        transaction_id="transaction:death-confirm", idempotency_key="death-confirm", expected_revisions={source_stream: 1},
        causation_id="case-death", correlation_id="case", source_ref=source_event.event_id, submitted_at="now",
    )
    intent = WorldDeathConfirmationIntent(
        source_event_id=source_event.event_id, target_actor_ref="character:survivor", expected_source_revision=1,
        confirmation_ref="confirmation:case:1", confirmed=True, policy_revision="policy:death@1",
    )
    assert authority.confirm_world_death(command=command, intent=intent).committed

    changed = authority.confirm_world_death(
        command=command.model_copy(update={"command_id": "death-confirm:changed"}), intent=intent,
    )

    assert not changed.committed
    assert changed.error_code == "world_death_idempotency_reused"


def test_world_death_confirmation_durable_reopen_full_and_checkpoint_tail(tmp_path) -> None:
    path = tmp_path / "death.db"
    store = DurableGameplayEventStore(path)
    source_stream = "gameplay:conflict:encounter:case"
    source = store.append_batch(build_atomic_event_batch(
        command_id="case-death", principal_ref="authority:p5:investigation-conflict",
        stream_id=source_stream, expected_revision=0,
        event_specs=(("gameplay.conflict.terminal_outcome_recorded", {"actor_ref": "character:survivor", "terminal_kind": "case_death"}),),
        idempotency_key="case-death", causation_id="case", correlation_id="case",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    authority = InvestigationConflictAuthority(registry=_registry(), store=store)
    command = GameplayCommandEnvelope(
        command_id="death-confirm", command_type="gameplay.conflict.confirm_world_death", command_version=1,
        principal_ref="authority:p5:investigation-conflict", actor_ref="character:survivor", project_ref="project:case",
        transaction_id="transaction:death-confirm", idempotency_key="death-confirm", expected_revisions={source_stream: 1},
        causation_id="case-death", correlation_id="case", source_ref=source_event.event_id, submitted_at="now",
    )
    intent = WorldDeathConfirmationIntent(
        source_event_id=source_event.event_id, target_actor_ref="character:survivor", expected_source_revision=1,
        confirmation_ref="confirmation:case:1", confirmed=True, policy_revision="policy:death@1",
    )
    assert authority.confirm_world_death(command=command, intent=intent).committed
    full_before = authority.replay_full(now="now")
    prefix = store.read_events(limit=1)
    prefix_state = authority._projection_state(prefix)
    checkpoint = ProjectionCheckpoint(
        checkpoint_id="checkpoint:death:1", projector_id="projector:p5:investigation-conflict", projector_version="v1",
        projection_schema_version=1, source_revision_vector=dict(prefix_state["source_revision_vector"]),
        last_global_sequence=prefix_state["last_global_sequence"], state=prefix_state,
        applied_event_ids=list(prefix_state["applied_event_ids"]), projection_hash=canonical_sha256_digest(prefix_state),
        registry_revision=_registry().registry_revision,
    )
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        restored = InvestigationConflictAuthority(registry=_registry(), store=reopened)
        full_after = restored.replay_full(now="now")
        tail = restored.replay_checkpoint_tail(checkpoint=checkpoint, now="now")
        assert full_after.projection_hash == full_before.projection_hash
        assert tail.projection_hash == full_after.projection_hash
        assert tail.state == full_after.state
        assert restored.confirm_world_death(command=command, intent=intent).idempotency_status == "duplicate_replayed"
    finally:
        reopened.close()
