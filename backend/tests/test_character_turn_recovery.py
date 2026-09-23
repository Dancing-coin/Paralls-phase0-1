from pathlib import Path

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
