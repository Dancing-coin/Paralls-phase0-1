from copy import deepcopy
from pathlib import Path
import shutil

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_continuity_store import (
    CharacterGraphContinuityStore,
)
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:turn-recovery",
        session_id="session:turn-recovery",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def runtime_with_graph_and_session(tmp_path: Path) -> CharacterAgentRuntime:
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "turn-recovery.sqlite3")
    return CharacterAgentRuntime(
        session_store=CharacterAgentSessionStore(tmp_path / "session"),
        continuity_actor_ids={"char_b"},
        continuity_store=CharacterGraphContinuityStore(
            graph,
            scope_resolver=_scope,
            require_complete_snapshot=True,
        ),
    )


def test_restart_marks_unreceipted_execution_recovery_required(tmp_path: Path) -> None:
    """A restart must never resend an unresolved authority request."""
    runtime = runtime_with_graph_and_session(tmp_path)
    turn = runtime.begin_test_turn_awaiting_settlement(
        "char_b", request_ref="request:door:1"
    )
    runtime.flush_continuity_snapshot("char_b")

    restored = runtime_with_graph_and_session(tmp_path)
    result = restored.reconcile_character_turn("char_b")

    assert result.status == "recovery_required"
    assert result.turn_id == turn.turn_id
    assert restored.outgoing_authority_request_count(turn.turn_id) == 0


def _rewrite_snapshot(
    runtime: CharacterAgentRuntime,
    actor_id: str,
    snapshot: dict[str, object],
    source_ref: str,
) -> None:
    snapshot["graph_source_event_ref"] = source_ref
    snapshot["snapshot_digest"] = runtime._continuity_snapshot_digest(snapshot)
    runtime._continuity_store.write_snapshot(
        actor_id=actor_id,
        producer_ts=2,
        source_event_ref=source_ref,
        snapshot=snapshot,
    )


def test_malformed_active_turn_is_durably_blocked(tmp_path: Path) -> None:
    runtime = runtime_with_graph_and_session(tmp_path)
    turn = runtime.begin_test_turn_awaiting_settlement("char_b", "request:bad-active")
    runtime.flush_continuity_snapshot("char_b")
    snapshot = runtime._continuity_store.read_snapshot("char_b")
    assert snapshot is not None
    snapshot.pop("_continuity_source_event_ref", None)
    snapshot["active_turns"][turn.turn_id]["stage_refs"]["bogus"] = "stage:bogus"
    _rewrite_snapshot(runtime, "char_b", snapshot, "tamper:active-turn")

    result = runtime._turn_recovery_service.reconcile("char_b")

    assert result.status == "recovery_required"
    assert result.reason == "active_turns_invalid"
    durable = runtime._continuity_store.read_snapshot("char_b")
    assert durable["policy_state"]["execution_blocked"] is True
    assert durable["session_timeline"][-1]["event_type"] == "character_turn_recovery_required"


def test_identical_duplicate_event_id_is_rejected_and_blocked(tmp_path: Path) -> None:
    runtime = runtime_with_graph_and_session(tmp_path)
    runtime.begin_test_turn_awaiting_settlement("char_b", "request:duplicate")
    runtime.flush_continuity_snapshot("char_b")
    snapshot = runtime._continuity_store.read_snapshot("char_b")
    assert snapshot is not None
    snapshot.pop("_continuity_source_event_ref", None)
    snapshot["session_timeline"].append(deepcopy(snapshot["session_timeline"][0]))
    _rewrite_snapshot(runtime, "char_b", snapshot, "tamper:duplicate-event")

    result = runtime._turn_recovery_service.reconcile("char_b")

    assert result.status == "recovery_required"
    assert result.reason == "timeline_invalid"
    durable = runtime._continuity_store.read_snapshot("char_b")
    assert durable["policy_state"]["execution_blocked"] is True


def test_graph_only_reconcile_commits_all_pending_turns_in_one_complete_checkpoint(
    tmp_path: Path,
) -> None:
    runtime = runtime_with_graph_and_session(tmp_path)
    turns = [
        runtime.begin_test_turn_awaiting_settlement("char_b", f"request:multi:{index}")
        for index in range(2)
    ]
    for index, turn in enumerate(turns, start=1):
        execution = turn.stage_events["execution"]
        runtime._session_store.append_event(
            actor_id="char_b",
            event_type="character_turn_authority_receipt",
            producer_ts=index + 1,
            expected_revision=runtime._session_store.event_count("char_b"),
            payload={
                "turn_id": turn.turn_id,
                "authority_request_ref": execution.payload["authority_request_ref"],
                "expected_revision": execution.payload["expected_revision"],
                "idempotency_key": execution.idempotency_key,
                "receipt_ref": f"receipt:multi:{index}",
                "producer_ts": index + 1,
            },
        )
    runtime.flush_continuity_snapshot("char_b")
    shutil.rmtree(tmp_path / "session")

    restored = runtime_with_graph_and_session(tmp_path)
    snapshot = restored._continuity_store.read_snapshot("char_b")
    assert snapshot is not None
    assert all(
        snapshot["active_turns"][turn.turn_id]["lifecycle"] == "committed"
        for turn in turns
    )
    assert snapshot["pending_execution"] == {}
    assert snapshot["checkpoint_event_index"] == len(snapshot["session_timeline"])
    assert snapshot["session_timeline_checkpoint_index"] == len(
        snapshot["session_timeline"]
    )
    assert sum(
        event["event_type"] == "character_turn_stage_recorded"
        and event["payload"].get("stage") in {"settlement", "evaluation", "policy"}
        for event in snapshot["session_timeline"]
    ) == 6

    shutil.rmtree(tmp_path / "session")
    graph_only_restart = runtime_with_graph_and_session(tmp_path)
    result = graph_only_restart.reconcile_character_turn("char_b")
    assert result.status == "already_committed"
