import pytest

from app.character_agent.memory.working_memory import CharacterWorkingMemory
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from test_character_graph_memory_store import _event, _scope


def percept():
    return _event("character_perceived_event", "evt:hot-read", 100, {
        "summary": "crate is closed", "target_object_id": "obj_crate", "percept_channel": "visual",
        "fact_claim": {"scope_ref": "room_demo", "subject_ref": "obj_crate", "predicate": "state",
                       "value": "closed", "valid_at": 100, "source_ref": "evt:hot-read"},
    })


def test_typed_history_read_preserves_records_without_folding_unused_working_memory(monkeypatch):
    events = [percept(), _event("unrelated", "evt:other", 101, {})]
    oracle = CharacterAgentMemoryStore()
    for event in events:
        oracle.write_event(event)
    expected = oracle.retrieval_record_bundle("char_b")
    store = CharacterAgentMemoryStore()
    store.bind_session_reader(lambda actor: events if actor == "char_b" else [])
    with monkeypatch.context() as guard:
        guard.setattr(CharacterWorkingMemory, "remember_event",
                      lambda *_: pytest.fail("typed read folded unused working memory"))
        assert store.retrieval_record_bundle("char_b") == expected
    assert store.retrieval_bundle("char_b")["working_memory"] == oracle.retrieval_bundle("char_b")["working_memory"]


def test_working_memory_recent_window_keeps_latest_entries_bounded():
    working = CharacterWorkingMemory()
    for index in range(40):
        working.remember_event(
            "char_a",
            {"event_type": "character_perceived_event", "event_index": index},
        )
        working.remember_event(
            "char_a",
            {"event_type": "character_agent_settlement_result", "event_index": index},
        )
        working.remember_event(
            "char_a",
            {"event_type": "siming_output_event", "event_index": index},
        )

    state = working.build_state("char_a", max_entries=32)

    assert len(state.recent_perceived_events) == 32
    assert len(state.recent_esm_results) == 32
    assert len(state.recent_siming_catalysts) == 32
    assert state.recent_perceived_events[0]["event_index"] == 8
    assert state.recent_esm_results[-1]["event_index"] == 39


def test_filtered_working_memory_reader_matches_full_history_without_scanning_it():
    events = [percept(), _event("unrelated", "evt:other", 101, {}),
              _event("siming_output_event", "evt:siming", 102, {"summary": "next scene"})]
    oracle = CharacterAgentMemoryStore()
    oracle.bind_session_reader(lambda _: events)
    store = CharacterAgentMemoryStore()

    def unbounded(_):
        pytest.fail("working memory must not scan unrelated session history")

    store.bind_session_reader(unbounded, working_reader=lambda _: [events[0], events[2]])
    assert store.working_memory_state("char_b") == oracle.working_memory_state("char_b")


def test_runtime_working_memory_reads_indexed_pages_in_original_order(tmp_path, monkeypatch):
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
    from app.character_agent.memory.working_memory import CharacterWorkingMemory

    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        session = runtime._session_store
        with session.transaction():
            for index in range(1000):
                session.append_event("char_a", "unrelated", index, {})
            for index in range(130):
                session.append_event("char_a", "character_perceived_event", 1000 + index, {"summary": str(index)})
        oracle = CharacterAgentMemoryStore()
        oracle.bind_session_reader(session.list_events)
        expected = oracle.working_memory_state("char_a")
        read_page = session.read_events_page
        calls = []

        def tracked_page(actor_id, **kwargs):
            calls.append(kwargs)
            return read_page(actor_id, **kwargs)

        monkeypatch.setattr(session, "read_events_page", tracked_page)
        monkeypatch.setattr(runtime._memory_store, "_session_reader",
                            lambda _: pytest.fail("working memory scanned full session history"))
        assert runtime.get_working_memory_state_record("char_a") == expected
        assert len(calls) == 2
        assert all(set(call["event_types"]) == CharacterWorkingMemory.RELEVANT_EVENT_TYPES for call in calls)
        assert [call["after_index"] for call in calls] == [0, 1128]
    finally:
        runtime.close()


@pytest.mark.parametrize("sqlite", [False, True])
def test_session_bound_memory_write_uses_atomic_receipts_without_scanning_pools(tmp_path, monkeypatch, sqlite):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / "graph.sqlite3") if sqlite else InMemoryHeavenlyGraphAdapter()
    try:
        for _ in range(2):
            store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
            store.bind_session_reader(lambda *_: [])
            with monkeypatch.context() as guard:
                guard.setattr(graph, "query_semantic", lambda *_: pytest.fail("hot write scanned memory pools"))
                store.write_event(percept())
                store.write_event(percept())
        oracle = CharacterAgentMemoryStore()
        oracle.write_event(percept())
        assert store.retrieval_record_bundle("char_b") == oracle.retrieval_record_bundle("char_b")
    finally:
        if sqlite:
            graph.close()


@pytest.mark.parametrize("history", [1000, 10000])
def test_filtered_session_read_work_is_independent_of_unrelated_history(tmp_path, history):
    store = CharacterAgentSessionStore(tmp_path)
    try:
        with store.transaction():
            for index in range(history):
                store.append_event("char_a", "unrelated", index, {})
            expected = store.append_event("char_a", "goal_state_event", history, {})
        steps = 0

        def count_step():
            nonlocal steps
            steps += 1
            return 0

        store._connection.set_progress_handler(count_step, 1)
        try:
            result = store.read_events_page("char_a", through_index=history + 1,
                event_types=("goal_state_event", "l2_reasoning_request"), limit=history + 1)
        finally:
            store._connection.set_progress_handler(None, 0)
        assert result == [expected]
        assert steps < 500, f"filtered read executed {steps} SQLite steps for {history} unrelated events"
    finally:
        store.close()
