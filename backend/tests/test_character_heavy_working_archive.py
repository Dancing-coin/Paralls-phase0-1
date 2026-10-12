import json
import sqlite3

import pytest

from app import main
from app.config import Settings
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.character_agent.storage.graph_memory_store import CharacterGraphMemoryStore
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from test_character_graph_memory_store import _event, _scope
from test_character_memory_projection_pages import _fill_history, _LegacyMemoryStore


def _bytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _heavy_state(tmp_path):
    state = main.build_runtime_state(Settings(siming_heavenly_mode="off", heavenly_graph_path=str(tmp_path / "graph.sqlite3")))
    try:
        runtime = state.character_agent_runtime
        _fill_history(runtime._session_store)
        for actor_id in runtime._session_store.actor_ids():
            for event in runtime._session_store.list_events(actor_id):
                runtime._project_session_event(event)
        return state
    except BaseException:
        state.close()
        raise


def test_heavy_archive_keeps_entire_bundle_and_validation_without_whole_history_list(tmp_path, monkeypatch):
    state = _heavy_state(tmp_path)
    try:
        runtime = state.character_agent_runtime
        graph_store = runtime._memory_store._graph
        assert runtime._memory_store._store_for("char_b") is graph_store
        expected = runtime.get_memory_bundle("char_b")
        assert len(expected["working_memory"]) == 268
        assert expected["working_memory"][-1]["event_type"] == "unknown_future_event"
        assert expected["working_memory"][1]["payload"]["snapshot_summary"] == {
            "visible_entities_count": 0, "audible_entities_count": 0, "attention_targets_count": 0, "focus_target": "",
        }
        monkeypatch.setattr(graph_store._normalizer, "_session_reader",
            lambda _: pytest.fail("heavy archive materialized entire history list"))
        ingest = CharacterAgentMemoryStore._ingest_event
        ingested_types = []

        def tracked_ingest(projection, event, *, include_working=True):
            ingested_types.append(event["event_type"])
            assert include_working
            return ingest(projection, event, include_working=include_working)

        monkeypatch.setattr(CharacterAgentMemoryStore, "_ingest_event", tracked_ingest)
        actual = runtime.get_memory_bundle("char_b")
        assert _bytes(actual) == _bytes(expected)
        assert len(ingested_types) == 268
        assert "character_memory_correction" in ingested_types
        assert ingested_types[-1] == "unknown_future_event"
        actual["working_memory"][-1]["payload"]["must_remain_in_working_archive"] = False
        assert runtime._session_store.read_events_page("char_b", after_index=267)[0]["payload"] == {
            "must_remain_in_working_archive": True,
        }
        assert _bytes(runtime.get_memory_bundle("char_b")) == _bytes(expected)
    finally:
        state.close()


def test_heavy_archive_reads_all_events_in_order_with_fixed_prefix(tmp_path, monkeypatch):
    state = _heavy_state(tmp_path)
    try:
        runtime = state.character_agent_runtime
        session = runtime._session_store
        expected = runtime.get_memory_bundle("char_b")
        read_page = session.read_events_page
        pages = []

        def tracked_page(actor_id, **kwargs):
            page = read_page(actor_id, **kwargs)
            pages.append((actor_id, kwargs, [event["event_index"] for event in page]))
            if len(pages) == 1:
                session.append_event("char_b", "unknown_future_event", 300, {"summary": "after prefix"})
            return page

        monkeypatch.setattr(session, "read_events_page", tracked_page)
        assert _bytes(runtime.get_memory_bundle("char_b")) == _bytes(expected)
        assert len(pages) == 3
        assert all(actor == "char_b" and call["event_types"] is None and call["through_index"] == 268
            and call["limit"] == 128 for actor, call, _ in pages)
        assert [index for _, _, indexes in pages for index in indexes] == list(range(1, 269))
    finally:
        state.close()


@pytest.mark.parametrize("field,value,error", [
    ("actor_id", "char_c", "correction actor mismatch"),
    ("confidence", "invalid-confidence", "confidence"),
])
def test_heavy_archive_preserves_typed_history_rejection_after_cold_restart(tmp_path, field, value, error):
    state = _heavy_state(tmp_path)
    state.close()
    with sqlite3.connect(tmp_path / "graph.sqlite3") as connection:
        event = json.loads(connection.execute(
            "SELECT payload_json FROM character_session_events WHERE actor_id=? AND event_type=?",
            ("char_b", "character_memory_correction"),
        ).fetchone()[0])
        event["payload"]["knowledge"][field] = value
        connection.execute(
            "UPDATE character_session_events SET payload_json=? WHERE actor_id=? AND event_type=?",
            (json.dumps(event), "char_b", "character_memory_correction"),
        )
    state = main.build_runtime_state(Settings(siming_heavenly_mode="off", heavenly_graph_path=str(tmp_path / "graph.sqlite3")))
    try:
        runtime = state.character_agent_runtime
        with pytest.raises(ValueError, match=error):
            runtime._memory_store._graph._normalizer.retrieval_bundle("char_b")
        with pytest.raises(ValueError, match=error):
            runtime.get_memory_bundle("char_b")
    finally:
        state.close()


@pytest.mark.parametrize("indexes", [(), (2,)])
def test_full_archive_rejects_empty_or_gapped_prefix_page(tmp_path, monkeypatch, indexes):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        monkeypatch.setattr(runtime._session_store, "event_count", lambda _: 10)
        calls = 0

        def bad_page(actor_id, **kwargs):
            nonlocal calls
            calls += 1
            if calls > 2:
                pytest.fail("archive repeated a gapped page")
            return [{"actor_id": actor_id, "event_index": index, "event_type": "unknown"} for index in indexes]

        monkeypatch.setattr(runtime._session_store, "read_events_page", bad_page)
        with pytest.raises(ValueError, match="character_session_event_index_mismatch"):
            list(runtime._memory_history_events("char_b"))
        assert calls == 1
    finally:
        runtime.close()


def test_full_working_archive_keeps_public_nested_values_isolated():
    event = _event("unknown_future_event", "event:archive", 1, {"nested": ["original"]})
    memory = CharacterAgentMemoryStore()
    memory.bind_session_reader(lambda _: [event])
    memory.bind_archive_reader(lambda _: iter([event]))
    archive = memory.retrieval_bundle("char_b")["working_memory"]
    archive[0]["payload"]["nested"].append("changed")
    assert event["payload"]["nested"] == ["original"]
    assert memory.retrieval_bundle("char_b")["working_memory"][0]["payload"]["nested"] == ["original"]


def test_runtime_preserves_legacy_custom_list_reader_with_archive_capability(tmp_path):
    memory = _LegacyMemoryStore()
    runtime = CharacterAgentRuntime(storage_root=tmp_path, memory_store=memory)
    try:
        assert isinstance(memory.reader("char_b"), list)
    finally:
        runtime.close()


def test_standalone_graph_archive_and_legacy_continuity_keep_previous_output(monkeypatch):
    graph = InMemoryHeavenlyGraphAdapter()
    store = CharacterGraphMemoryStore(graph, scope_resolver=_scope)
    event = _event("character_perceived_event", "event:standalone", 1, {"summary": "original"})
    store.write_event(event)
    assert store.retrieval_bundle("char_b")["working_memory"] == [event]
    legacy = CharacterGraphMemoryStore(InMemoryHeavenlyGraphAdapter(), scope_resolver=_scope,
        continuity_reader=lambda _: {"working_memory": {"recent_perceived_events": [{"event_type": "legacy"}]}})
    monkeypatch.setattr(legacy._normalizer, "retrieval_bundle",
        lambda _: pytest.fail("legacy continuity called fallback archive"))
    assert legacy.retrieval_bundle("char_b")["working_memory"] == [{"event_type": "legacy"}]
