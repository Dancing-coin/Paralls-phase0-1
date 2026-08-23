from pathlib import Path

import pytest

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.event_store import GameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from app.services.embodied_harness_task import (
    EmbodiedHarnessTaskCoordinator,
    HarnessCapabilityError,
    map_embodied_failure,
)
from app.services.embodied_interaction_session_service import (
    EmbodiedInteractionSessionService,
)
from app.services.harness_execution_trace import HarnessExecutionTraceService
from app.services.harness_capability_store import HarnessCapabilityStore


def _services() -> tuple[
    EmbodiedHarnessTaskCoordinator,
    EmbodiedInteractionSessionService,
    GameplayEventStore,
    EmbodiedEvidenceLedger,
]:
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    evidence = EmbodiedEvidenceLedger()
    session = EmbodiedInteractionSessionService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=evidence,
    )
    coordinator = EmbodiedHarnessTaskCoordinator(
        session_service=session,
        trace=HarnessExecutionTraceService(),
        evidence_ledger=evidence,
    )
    return coordinator, session, store, evidence


def test_embodied_task_runs_real_session_authority_and_evidence_chain() -> None:
    coordinator, _session, store, evidence = _services()

    result = coordinator.run_handshake(
        session_id="session:harness:1",
        initiator_ref="character:siming",
        participant_refs=["character:siming", "character:maya"],
        target_refs=["character:maya"],
        policy_revision=3,
        scene_revision=11,
    )

    assert result.accepted is True
    assert result.phase == "committed"
    assert [event.event_type for event in store.read_stream("session:session:harness:1")][-1] == "embodied.interaction_session.committed"
    assert len(evidence.events_for_attempt("session:harness:1")) >= 1
    trace = coordinator.trace.get_trace("session:harness:1")
    assert trace[-1].status == "committed"
    assert trace[-1].metadata["authority_event_ids"]
    assert trace[-1].metadata["evidence_count"] >= 1


def test_embodied_failure_mapping_is_closed_and_recovery_specific() -> None:
    assert map_embodied_failure("session_not_authorized").kind == "constraint_conflict"
    assert map_embodied_failure("participant_unknown").kind == "invalid_input"
    assert map_embodied_failure("append_batch_failed").kind == "transient"
    assert map_embodied_failure("unknown_error").kind == "unknown"


def test_capability_gate_rejects_commit_before_approval() -> None:
    coordinator, _session, _store, _evidence = _services()
    with pytest.raises(HarnessCapabilityError, match="capability phase"):
        coordinator.gate.require("commit")


def test_trace_redacts_secrets_and_rejects_private_payloads() -> None:
    trace = HarnessExecutionTraceService()
    trace.start(task_id="task:redact", run_id="run:redact", correlation_id="corr:redact")
    record = trace.record(
        "task:redact",
        stage="inspect",
        status="observed",
        producer_ts=1,
        metadata={"api_key": "secret", "result_ref": "result:1"},
    )
    assert record.metadata["api_key"] == "[REDACTED]"
    with pytest.raises(ValueError, match="metadata field forbidden"):
        trace.record(
            "task:redact",
            stage="inspect",
            status="rejected",
            producer_ts=2,
            metadata={"chain_of_thought": "private"},
        )


def test_committed_task_recovers_without_duplicate_authority_events(tmp_path: Path) -> None:
    ledger_path = tmp_path / "harness-task-ledger.json"
    store = GameplayEventStore()
    bus = InMemoryAuthorityEventBus()
    evidence = EmbodiedEvidenceLedger()
    session = EmbodiedInteractionSessionService(
        store=store,
        dispatcher=GameplayOutboxDispatcher(store=store, bus=bus),
        evidence_ledger=evidence,
    )
    trace = HarnessExecutionTraceService(storage_path=ledger_path)
    coordinator = EmbodiedHarnessTaskCoordinator(session_service=session, trace=trace)
    first = coordinator.run_handshake(
        session_id="session:harness:recover",
        initiator_ref="character:siming",
        participant_refs=["character:siming", "character:maya"],
        target_refs=["character:maya"],
        policy_revision=3,
        scene_revision=11,
    )
    event_count = len(store.read_events())

    restored_trace = HarnessExecutionTraceService(storage_path=ledger_path)
    restored = EmbodiedHarnessTaskCoordinator(session_service=session, trace=restored_trace)
    recovered = restored.recover("session:harness:recover")

    assert first.phase == "committed"
    assert recovered.phase == "committed"
    assert len(store.read_events()) == event_count


def test_godot_projection_trace_keeps_only_safe_authority_refs() -> None:
    coordinator, _session, _store, _evidence = _services()
    coordinator.trace.start(task_id="task:projection", run_id="run:projection", correlation_id="corr:projection")
    coordinator.trace.transition("task:projection", "running", producer_ts=1)
    coordinator.record_godot_projection(
        "task:projection",
        [{
            "message_type": "embodied_interaction_session_event",
            "payload": {
                "event_id": "evt:1",
                "transaction_id": "tx:1",
                "global_sequence": 4,
                "session_id": "session:1",
                "participant_private_terms": {"hidden": "no"},
            },
        }],
        producer_ts=2,
    )
    metadata = coordinator.trace.get_trace("task:projection")[-1].metadata
    assert metadata["projection_refs"] == [{
        "message_type": "embodied_interaction_session_event",
        "event_id": "evt:1",
        "transaction_id": "tx:1",
        "global_sequence": 4,
        "session_id": "session:1",
    }]


def test_evidence_join_records_bounded_terminal_references_without_payloads() -> None:
    coordinator, _session, _store, _evidence = _services()
    coordinator.trace.start(task_id="task:evidence", run_id="run:evidence", correlation_id="corr:evidence")
    coordinator.trace.transition("task:evidence", "running", producer_ts=1)
    coordinator.record_evidence_join(
        "task:evidence",
        authority_result_ref="authority:result:1",
        gameplay_transaction_id="tx:1",
        gameplay_event_ids=["evt:1"],
        outbox_delivery_refs=["outbox:1"],
        godot_receipt_ref="godot:receipt:1",
        replay_hash="sha256:1",
        verifier_run_id="run:verify:1",
        producer_ts=2,
    )
    metadata = coordinator.trace.get_trace("task:evidence")[-1].metadata
    assert metadata["gameplay_event_ids"] == ["evt:1"]
    assert "payload" not in metadata


def test_waiting_task_recovers_and_finishes_without_replaying_authority_prefix() -> None:
    coordinator, _session, store, _evidence = _services()
    started = coordinator.run_handshake(
        session_id="session:harness:waiting",
        initiator_ref="character:siming",
        participant_refs=["character:siming", "character:maya"],
        target_refs=["character:maya"],
        policy_revision=3,
        scene_revision=11,
        complete=False,
    )
    prefix_count = len(store.read_events())
    recovered = coordinator.recover("session:harness:waiting")
    first = coordinator.record_terminal_observation(
        task_id="session:harness:waiting",
        participant_ref="character:siming",
        attempt_ref="attempt:waiting:siming",
        terminal_status="completed",
        payload_digest="digest:waiting:siming",
        producer_ts=10,
    )
    committed = coordinator.record_terminal_observation(
        task_id="session:harness:waiting",
        participant_ref="character:maya",
        attempt_ref="attempt:waiting:maya",
        terminal_status="completed",
        payload_digest="digest:waiting:maya",
        producer_ts=11,
    )

    assert started.phase == "waiting"
    assert recovered.accepted is True
    assert first.phase == "waiting"
    assert committed.phase == "committed"
    assert len(store.read_events()) > prefix_count
    assert len(store.read_stream("session:session:harness:waiting")) == 7


def test_embodied_task_uses_persistent_capability_grants(tmp_path: Path) -> None:
    store = GameplayEventStore()
    evidence = EmbodiedEvidenceLedger()
    session = EmbodiedInteractionSessionService(store=store, evidence_ledger=evidence)
    coordinator = EmbodiedHarnessTaskCoordinator(
        session_service=session,
        trace=HarnessExecutionTraceService(),
        evidence_ledger=evidence,
        capability_store=HarnessCapabilityStore(tmp_path / "capabilities.sqlite3"),
    )
    result = coordinator.run_handshake(
        session_id="session:harness:capability",
        initiator_ref="character:siming",
        participant_refs=["character:siming", "character:maya"],
        target_refs=["character:maya"],
        policy_revision=3,
        scene_revision=11,
    )
    assert result.phase == "committed"
    persisted = HarnessCapabilityStore(tmp_path / "capabilities.sqlite3")
    assert persisted.read("harness:session:harness:capability:commit:0").state == "consumed"
