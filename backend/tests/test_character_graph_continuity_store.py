import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

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


def test_same_actor_graph_flush_serializes_snapshot_capture(monkeypatch) -> None:
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter

    store = CharacterGraphContinuityStore(
        InMemoryHeavenlyGraphAdapter(), scope_resolver=_scope
    )
    runtime = CharacterAgentRuntime(continuity_store=store)
    first_write_entered, release_first, second_started = Event(), Event(), Event()
    second_capture_entered = Event()
    write_current = store.write_current_state
    read_count = runtime._session_timeline_event_count
    sources: list[str] = []

    def blocking_write(**kwargs):
        if not sources:
            first_write_entered.set()
            assert release_first.wait(5)
        sources.append(kwargs["source_event_ref"])
        write_current(**kwargs)

    def record_capture(actor_id):
        if second_started.is_set():
            second_capture_entered.set()
        return read_count(actor_id)

    def second_flush():
        second_started.set()
        runtime._persist_graph_continuity(actor_id="char_b", producer_ts=2)

    monkeypatch.setattr(store, "write_current_state", blocking_write)
    monkeypatch.setattr(runtime, "_session_timeline_event_count", record_capture)
    first = runtime._session_store.append_event("char_b", "probe", 1, {})
    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            runtime._persist_graph_continuity, actor_id="char_b", producer_ts=1
        )
        try:
            assert first_write_entered.wait(5)
            second = runtime._session_store.append_event("char_b", "probe", 2, {})
            second_future = executor.submit(second_flush)
            assert second_started.wait(5)
            # 第一份快照尚未提交，第二次 flush 不得捕获更晚状态抢先写入。
            assert not second_capture_entered.wait(0.1)
        finally:
            release_first.set()
        first_future.result(timeout=5)
        second_future.result(timeout=5)
    assert sources == [first["event_id"], second["event_id"]]
    restored = store.read_current_state("char_b")
    assert restored[store.SOURCE_EVENT_REF_FIELD] == second["event_id"]


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


def test_production_continuity_store_rejects_partial_snapshot() -> None:
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter

    store = CharacterGraphContinuityStore(
        InMemoryHeavenlyGraphAdapter(),
        scope_resolver=_scope,
        require_complete_snapshot=True,
    )

    try:
        store.write_snapshot(
            actor_id="char_b",
            producer_ts=100,
            snapshot={"working_memory": {}},
            source_event_ref="event:partial",
        )
    except ValueError as exc:
        assert "missing required field" in str(exc)
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("partial production continuity snapshot was accepted")


def test_runtime_requires_graph_continuity_store_in_production_mode(monkeypatch) -> None:
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime

    monkeypatch.setenv("CHARACTER_GRAPH_REQUIRE_CONTINUITY", "1")
    try:
        try:
            CharacterAgentRuntime()
        except ValueError as exc:
            assert "graph continuity store is required" in str(exc)
        else:  # pragma: no cover
            raise AssertionError("production runtime accepted missing continuity store")
    finally:
        monkeypatch.delenv("CHARACTER_GRAPH_REQUIRE_CONTINUITY", raising=False)


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
    timeline_before_restart = first.character_agent_runtime.get_session_timeline("char_b")
    first.close()
    session_root = graph_path.parent / f"{graph_path.name}.character-agent"
    shutil.rmtree(session_root)

    second = main.build_runtime_state(settings)
    try:
        assert second.character_agent_runtime.get_dynamic_state("char_b") != {}
        assert second.character_agent_runtime.get_need_tension_state("char_b")["actor_id"] == "char_b"
        assert second.character_agent_runtime.get_runtime_continuity_state("char_b")["actor_id"] == "char_b"
        assert second.character_agent_runtime.get_memory_bundle("char_b")["working_memory"]
        second.character_agent_runtime.ingest_character_perceived_event(
            CharacterPerceivedEvent(
                actor_id="char_b",
                percept_channel="visual",
                producer_ts=202,
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                perceived_summary="obj_letter remains visible",
                source_candidate_event_id="visual:continuity:202",
            )
        )
        timeline_after_restart = second.character_agent_runtime.get_session_timeline("char_b")
        assert [event["event_id"] for event in timeline_after_restart[: len(timeline_before_restart)]] == [
            event["event_id"] for event in timeline_before_restart
        ]
        assert len(timeline_after_restart) > len(timeline_before_restart)
    finally:
        second.close()


def test_character_runtime_restores_complete_goal_history_from_graph(tmp_path: Path) -> None:
    graph_path = tmp_path / "goal-history.sqlite3"
    settings = config_module.Settings(
        heavenly_graph_path=str(graph_path), siming_heavenly_mode="off"
    )
    first = main.build_runtime_state(settings)
    goal_store = first.character_agent_runtime._goal_state_store
    goals = [
        {
            "primary_goal": "inspect the letter",
            "immediate_goal": "approach the table",
            "transition_kind": "initial",
        },
        {
            "primary_goal": "protect the letter",
            "immediate_goal": "keep watch",
            "transition_kind": "continued",
        },
    ]
    for producer_ts, goal in enumerate(goals, start=299):
        goal_store.write("char_b", goal)
        first.character_agent_runtime._session_store.append_event(
            actor_id="char_b",
            event_type="goal_state_event",
            producer_ts=producer_ts,
            payload=goal_store.read("char_b"),
        )
        first.character_agent_runtime._persist_graph_continuity(
            actor_id="char_b", producer_ts=producer_ts
        )
    expected_history = first.character_agent_runtime.get_goal_state_history("char_b")
    first.close()

    second = main.build_runtime_state(settings)
    try:
        assert second.character_agent_runtime.get_goal_state_history("char_b") == expected_history
    finally:
        second.close()


def test_runtime_ignores_graph_current_state_without_committed_source_event() -> None:
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter

    store = CharacterGraphContinuityStore(
        InMemoryHeavenlyGraphAdapter(),
        scope_resolver=_scope,
    )
    store.write_current_state(
        actor_id="char_a",
        producer_ts=500,
        source_event_ref="event:not-committed",
        snapshot={
            "continuity_revisions": 99,
            "continuity_receipts": {},
            "session_timeline_tail": [],
        },
    )

    runtime = CharacterAgentRuntime(continuity_store=store)

    assert runtime.get_continuity_revision("char_a") == 0


def test_goal_state_does_not_advance_when_session_append_fails(monkeypatch) -> None:
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
    from app.models.character_agent_runtime import CharacterIntentDecision

    runtime = CharacterAgentRuntime()

    def fail_append(*args, **kwargs):
        raise RuntimeError("session_append_failed")

    monkeypatch.setattr(runtime._session_store, "append_event", fail_append)

    with pytest.raises(RuntimeError, match="session_append_failed"):
        runtime._record_goal_state_event(
            "char_a",
            600,
            CharacterIntentDecision(
                actor_id="char_a",
                selected_intent="observe",
                persona_passed=True,
                logic_passed=True,
                gain_loss_passed=True,
                rationale="inspect first",
            ),
        )

    assert runtime.get_goal_state_history("char_a") == []
