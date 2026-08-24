from pathlib import Path

from app.character_agent.storage.graph_continuity_store import (
    CharacterGraphContinuityStore,
)
from app import config as config_module
from app import main
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(actor_id: str) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:continuity",
        session_id="session:continuity",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id=actor_id,
    )


def test_graph_continuity_snapshot_survives_sqlite_restart(tmp_path: Path) -> None:
    graph_path = tmp_path / "continuity.sqlite3"
    first_graph = SQLiteHeavenlyGraphAdapter(graph_path)
    first = CharacterGraphContinuityStore(first_graph, scope_resolver=_scope)
    first.write_snapshot(
        actor_id="char_b",
        producer_ts=100,
        snapshot={
            "working_memory": [{"event_type": "character_perceived_event"}],
            "dynamic_state": {"stress_load": 0.7},
            "need_tension_state": {"safety_pressure": 0.8},
            "supervision_state": {"current_level": "medium"},
            "goal_state": {"primary_goal": "protect the letter"},
            "session_timeline": [{"event_type": "goal_state_event"}],
            "continuity_state": {"last_transition_kind": "execution_requested"},
        },
        source_event_ref="event:continuity:100",
    )
    first_graph.close()

    second_graph = SQLiteHeavenlyGraphAdapter(graph_path)
    second = CharacterGraphContinuityStore(second_graph, scope_resolver=_scope)
    restored = second.read_snapshot("char_b", valid_at=100)
    second_graph.close()

    assert restored is not None
    assert restored["dynamic_state"]["stress_load"] == 0.7
    assert restored["need_tension_state"]["safety_pressure"] == 0.8
    assert restored["continuity_state"]["last_transition_kind"] == "execution_requested"


def test_character_runtime_rebuilds_state_from_graph_after_session_file_loss(
    tmp_path: Path,
) -> None:
    graph_path = tmp_path / "runtime-continuity.sqlite3"
    settings = config_module.Settings(
        heavenly_graph_path=str(graph_path), siming_heavenly_mode="off"
    )
    first = main.build_runtime_state(settings)
    first.character_agent_runtime.ingest_character_perceived_event(
        CharacterPerceivedEvent(
            actor_id="char_b",
            percept_channel="visual",
            producer_ts=200,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            perceived_summary="obj_letter is visible",
            source_candidate_event_id="visual:continuity:200",
        )
    )
    first.character_agent_runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=201,
        payload={
            "result_id": "result:continuity:201",
            "result_type": "constraint_state_result",
            "settlement_status": "rejected",
            "constraint_summary": "too far",
            "causation_id": "cause:continuity:201",
            "correlation_id": "corr:continuity:201",
        },
    )
    first.close()
    session_file = graph_path.parent / f"{graph_path.name}.character-agent" / "character_agent_session_store.json"
    session_file.unlink()

    second = main.build_runtime_state(settings)
    try:
        assert second.character_agent_runtime.get_dynamic_state("char_b") != {}
        assert second.character_agent_runtime.get_need_tension_state("char_b")["actor_id"] == "char_b"
        assert second.character_agent_runtime.get_runtime_continuity_state("char_b")["actor_id"] == "char_b"
        assert second.character_agent_runtime.get_memory_bundle("char_b")["working_memory"]
    finally:
        second.close()
