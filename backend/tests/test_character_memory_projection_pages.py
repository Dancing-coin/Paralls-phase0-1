import json

import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.memory_store_router import CharacterMemoryStoreRouter
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from test_character_graph_memory_store import _scope


def _fill_history(session):
    with session.transaction():
        for index in range(130):
            session.append_event("char_b", "character_perceived_event", index, {
                "summary": str(index), "target_object_id": "obj_crate", "percept_channel": "visual",
            })
            session.append_event("char_b", "l2_reasoning_request", index, {
                "unused_model_body": "unused-model-body:" + "x" * 65_536,
            })
        for kind, payload in (
            ("character_agent_settlement_result", {"result_type": "object_state_result", "change_summary": "done"}),
            ("character_agent_dialogue_response", {"content": "hello"}),
            ("relational_belief_event", {"entity_id": "char_c", "belief_type": "trust_level", "value": "guarded"}),
            ("knowledge_belief_event", {"proposition_key": "crate:closed", "proposition": "crate closed", "state": "believed"}),
            ("social_cognition_event", {"entity_id": "char_c", "trust_baseline": .4}),
            ("higher_order_belief_event", {"subject_actor_id": "char_c", "proposition_key": "crate:closed", "meta_belief": "char_c knows"}),
            ("character_memory_correction", {"knowledge": {
                "memory_id": "memory:correction", "actor_id": "char_b", "proposition_key": "crate:closed",
                "proposition": "crate closed", "state": "believed", "confidence": .8,
                "source_event_id": "event:correction-source", "producer_ts": 200,
            }}),
            ("unknown_future_event", {"must_remain_in_working_archive": True}),
        ):
            session.append_event("char_b", kind, 200, payload)
        session.append_event("char_c", "character_perceived_event", 200, {"summary": "other actor"})


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class _LegacyMemoryStore:
    def bind_session_reader(self, reader, *, working_reader=None, summary_reader=None):
        self.reader = reader


@pytest.mark.parametrize("field,value,old_error", [
    (None, None, None),
    ("confidence", "invalid-confidence", "confidence"),
    ("actor_id", "char_c", "correction actor mismatch"),
])
def test_typed_history_rejects_sql_type_that_shadows_correction(tmp_path, field, value, old_error):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        session = runtime._session_store
        event = session.append_event("char_b", "character_memory_correction", 1, {
            "knowledge": {
                "memory_id": "memory:correction", "actor_id": "char_b",
                "proposition_key": "crate:closed", "proposition": "crate closed",
                "state": "believed", "confidence": .8,
                "source_event_id": "event:correction-source", "producer_ts": 1,
            },
        })
        oracle = CharacterAgentMemoryStore()
        oracle.bind_session_reader(session.list_events)
        expected = oracle.retrieval_record_bundle("char_b").model_dump(mode="json")
        assert expected["knowledge_memories"]
        assert runtime._memory_store.retrieval_record_bundle("char_b").model_dump(mode="json") == expected
        if field is not None:
            event["payload"]["knowledge"][field] = value
        with session.transaction():
            session._connection.execute(
                "UPDATE character_session_events SET event_type=?,payload_json=? WHERE actor_id=? AND event_id=?",
                ("unknown_future_event", json.dumps(event), "char_b", event["event_id"]),
            )
        if old_error is None:
            assert oracle.retrieval_record_bundle("char_b").model_dump(mode="json") == expected
        else:
            with pytest.raises(ValueError, match=old_error):
                oracle.retrieval_record_bundle("char_b")
        with pytest.raises(ValueError, match="character_session_event_index_mismatch"):
            runtime._memory_store.retrieval_record_bundle("char_b")
        assert session.list_events("char_b") == [event]
    finally:
        runtime.close()


def test_typed_identity_check_is_bounded_and_installed_on_existing_database(tmp_path):
    session = CharacterAgentSessionStore(tmp_path)
    first = session.append_event("char_b", "character_perceived_event", 1, {"summary": "one"})
    second = session.append_event("char_b", "unknown_future_event", 2, {})
    other = session.append_event("char_c", "unknown_future_event", 1, {})
    with session.transaction():
        session._connection.execute("DROP INDEX character_session_event_type_mismatch")
        session._connection.execute("UPDATE character_session_events SET event_type='tampered' WHERE event_type='unknown_future_event'")
    before = session.list_all_events()
    session.close()
    reopened = CharacterAgentSessionStore(tmp_path)
    try:
        assert reopened.list_all_events() == before == {"char_b": [first, second], "char_c": [other]}
        assert reopened.read_events_page("char_b", through_index=1, event_types=("character_perceived_event",)) == [first]
        assert reopened.read_events_page("char_b", after_index=2, event_types=("character_perceived_event",)) == []
        assert reopened.read_events_page("char_b", event_types=()) == []
        with pytest.raises(ValueError, match="character_session_event_index_mismatch"):
            reopened.read_events_page("char_b", through_index=2, event_types=("character_perceived_event",))
        plan = reopened._connection.execute(
            "EXPLAIN QUERY PLAN SELECT 1 FROM character_session_events "
            "INDEXED BY character_session_event_type_mismatch WHERE actor_id=? AND event_index>? AND "
            + reopened._EVENT_TYPE_MISMATCH + " LIMIT 1", ("char_b", 0),
        ).fetchall()
        assert any("SEARCH" in row[3] and "character_session_event_type_mismatch" in row[3] for row in plan)
    finally:
        reopened.close()


def test_typed_identity_index_keeps_malformed_archive_for_read_failure(tmp_path):
    session = CharacterAgentSessionStore(tmp_path)
    session.append_event("char_b", "unknown_future_event", 1, {})
    with session.transaction():
        session._connection.execute("DROP INDEX character_session_event_type_mismatch")
        session._connection.execute("UPDATE character_session_events SET payload_json='{bad'")
    session.close()
    reopened = CharacterAgentSessionStore(tmp_path)
    try:
        assert reopened._connection.execute("SELECT payload_json FROM character_session_events").fetchall() == [("{bad",)]
        with pytest.raises(ValueError, match="character_session_event_index_mismatch"):
            reopened.read_events_page("char_b", event_types=("character_perceived_event",))
    finally:
        reopened.close()


def test_runtime_accepts_original_memory_store_binding_signature(tmp_path):
    memory = _LegacyMemoryStore()
    runtime = CharacterAgentRuntime(storage_root=tmp_path, memory_store=memory)
    try:
        event = runtime._session_store.append_event("char_b", "unknown", 1, {})
        assert list(memory.reader("char_b")) == [event]
    finally:
        runtime.close()


def test_memory_router_preserves_original_store_binding_signature():
    light, graph = _LegacyMemoryStore(), _LegacyMemoryStore()
    router = CharacterMemoryStoreRouter(light_store=light, graph_store=graph, heavy_actor_ids=frozenset())
    reader = lambda _: []
    router.bind_session_reader(reader)
    assert light.reader is reader and graph.reader is reader


@pytest.mark.parametrize("routed", [False, True])
def test_typed_memory_projection_reads_only_consumed_events_in_bounded_pages(tmp_path, monkeypatch, routed):
    memory = None
    if routed:
        memory = CharacterMemoryStoreRouter(light_store=CharacterAgentMemoryStore(),
            graph_store=CharacterGraphMemoryStore(InMemoryHeavenlyGraphAdapter(), scope_resolver=_scope),
            heavy_actor_ids=frozenset({"char_c"}))
    runtime = CharacterAgentRuntime(storage_root=tmp_path, memory_store=memory)
    try:
        session = runtime._session_store
        _fill_history(session)
        oracle = CharacterAgentMemoryStore()
        oracle.bind_session_reader(session.list_events)
        expected = oracle.retrieval_record_bundle("char_b").model_dump(mode="json")
        read_page = session.read_events_page
        loads = json.loads
        pages = []

        def tracked_page(actor_id, **kwargs):
            page = read_page(actor_id, **kwargs)
            pages.append((actor_id, kwargs, [event["event_index"] for event in page]))
            if len(pages) == 1:
                session.append_event("char_b", "character_perceived_event", 300, {"summary": "after prefix"})
            return page

        def checked_loads(raw, *args, **kwargs):
            if "unused-model-body:" in raw:
                pytest.fail("typed memory projection decoded unused model request history")
            return loads(raw, *args, **kwargs)

        monkeypatch.setattr(session, "read_events_page", tracked_page)
        monkeypatch.setattr(json, "loads", checked_loads)
        actual = runtime._memory_store.retrieval_record_bundle("char_b").model_dump(mode="json")
        assert _bytes(actual) == _bytes(expected)
        assert pages and all(actor == "char_b" for actor, _, _ in pages)
        assert all(call["through_index"] == 268 and call["limit"] == 128 for _, call, _ in pages)
        assert all("l2_reasoning_request" not in call["event_types"] for _, call, _ in pages)
        assert sum(len(indexes) for _, _, indexes in pages) == 137
        assert session.event_count("char_b") == 269
        assert [index for _, _, indexes in pages for index in indexes] == sorted(
            index for _, _, indexes in pages for index in indexes)
    finally:
        runtime.close()


def test_full_memory_projection_preserves_unknown_working_events_and_list_reader(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        session = runtime._session_store
        _fill_history(session)
        oracle = CharacterAgentMemoryStore()
        oracle.bind_session_reader(session.list_events)
        expected = oracle.retrieval_bundle("char_b")
        read_history = session.list_events
        calls = []

        def tracked_history(actor_id):
            history = read_history(actor_id)
            calls.append(actor_id)
            assert isinstance(history, list)
            return history

        monkeypatch.setattr(runtime._memory_store, "_session_reader", tracked_history)
        assert _bytes(runtime.get_memory_bundle("char_b")) == _bytes(expected)
        assert calls == ["char_b"]
        assert expected["working_memory"][-1]["event_type"] == "unknown_future_event"
        assert session.event_count("char_b") == 268
    finally:
        runtime.close()


@pytest.mark.parametrize("field,value", [("actor_id", "char_c"), ("event_index", 2), ("event_type", "other")])
def test_session_page_rejects_body_that_disagrees_with_sql_identity(tmp_path, field, value):
    session = CharacterAgentSessionStore(tmp_path)
    try:
        event = session.append_event("char_b", "character_perceived_event", 1, {"summary": "one"})
        with session.transaction():
            session._connection.execute("UPDATE character_session_events SET payload_json=? WHERE actor_id=?",
                (json.dumps({**event, field: value}), "char_b"))
        with pytest.raises(ValueError, match="character_session_event_index_mismatch"):
            session.read_events_page("char_b", event_types=("character_perceived_event",))
    finally:
        session.close()


@pytest.mark.parametrize("indexes", [(1,), (11,), (2, 1)])
def test_memory_projection_rejects_nonprogressing_or_out_of_prefix_page(tmp_path, monkeypatch, indexes):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        calls = 0
        monkeypatch.setattr(runtime._session_store, "event_count", lambda _: 10)

        def bad_page(actor_id, **kwargs):
            nonlocal calls
            calls += 1
            if calls > 3:
                pytest.fail("memory projection repeated a nonprogressing page")
            return [{"actor_id": actor_id, "event_index": index, "event_type": "character_perceived_event"}
                    for index in indexes]

        monkeypatch.setattr(runtime._session_store, "read_events_page", bad_page)
        with pytest.raises(ValueError, match="character_session_event_index_mismatch"):
            list(runtime._memory_history_events("char_b", event_types=("character_perceived_event",)))
    finally:
        runtime.close()
