import sqlite3

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.models import GameplayEvent
from test_gameplay_event_store_contract import _batch, _event


def history(store, count=1000):
    events = [{**_event(f"event:{i}", stream_id="stream:history"),
               "event_type": "selected" if i % 200 == 199 else "noise"} for i in range(count)]
    assert store.append_batch(_batch(events=events, expected={"stream:history": 0})).committed


@pytest.mark.parametrize("durable", [False, True])
def test_event_type_filter_limits_matches_after_global_cursor_and_detaches(tmp_path, durable):
    store = DurableGameplayEventStore(tmp_path / "events.sqlite3") if durable else GameplayEventStore()
    history(store)
    first = store.read_events(event_type="selected", global_sequence_after=200, limit=2)
    assert [row.global_sequence for row in first] == [400, 600]
    assert [row.global_sequence for row in store.read_events(event_type="selected", global_sequence_from=600, limit=2)] == [600, 800]
    first[0].payload["slot"] = "changed"
    assert store.read_events(event_type="selected", global_sequence_after=200, limit=1)[0].payload["slot"] == "stream:history"
    assert store.read_events(event_type="missing", limit=1) == []
    assert len(store.read_events(global_sequence_after=200, limit=2)) == 2


def test_sparse_query_uses_index_after_old_database_reopen_and_decodes_only_matches(tmp_path, monkeypatch):
    path = tmp_path / "events.sqlite3"
    original = DurableGameplayEventStore(path)
    history(original)
    before = original.export_snapshot()
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX IF EXISTS events_type_sequence")
    store = DurableGameplayEventStore(path)
    assert store.export_snapshot() == before
    with sqlite3.connect(path) as connection:
        plan = connection.execute("EXPLAIN QUERY PLAN SELECT value FROM events WHERE global_sequence>=? AND json_extract(value,'$.event_type')=? ORDER BY global_sequence LIMIT ?",
            (401, "selected", 2)).fetchall()
    assert any("events_type_sequence" in row[3] for row in plan)
    decoded = []
    validate = GameplayEvent.model_validate_json
    def checked(value, **kwargs):
        result = validate(value, **kwargs)
        decoded.append(result.event_type)
        return result
    monkeypatch.setattr(GameplayEvent, "model_validate_json", checked)
    assert [row.global_sequence for row in store.read_events(event_type="selected", global_sequence_after=400, limit=2)] == [600, 800]
    assert decoded == ["selected", "selected"]
