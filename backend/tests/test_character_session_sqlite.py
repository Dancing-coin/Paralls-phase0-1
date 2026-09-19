import json
import hashlib
import sqlite3

import pytest

from app.character_agent.storage.session_store import CharacterAgentSessionStore


@pytest.mark.parametrize("source", ["append", "json", "jsonl"])
def test_session_keeps_legacy_event_identity_scoped_to_actor(tmp_path, source):
    oracle = CharacterAgentSessionStore()
    first = oracle.append_event("a:b", "c", 1, {"owner": "first"})
    second = oracle.append_event("a", "b:c", 1, {"owner": "second"})
    assert first["event_id"] == second["event_id"]
    if source == "json":
        (tmp_path / "character_agent_session_store.json").write_text(json.dumps(oracle.list_all_events()), encoding="utf-8")
    elif source == "jsonl":
        actors = tmp_path / "character_agent_session_store" / "actors"
        actors.mkdir(parents=True)
        for event in (first, second):
            path = actors / (hashlib.sha256(event["actor_id"].encode()).hexdigest() + ".jsonl")
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    store = CharacterAgentSessionStore(tmp_path)
    try:
        if source == "append":
            store._runtime_id = oracle._runtime_id
            assert store.append_event("a:b", "c", 1, {"owner": "first"}) == first
            assert store.append_event("a", "b:c", 1, {"owner": "second"}) == second
        assert store.read_event("a:b", event_id=first["event_id"]) == first
        assert store.read_event("a", event_id=first["event_id"]) == second
        # 跨 actor 可同名，同 actor 的相同 ID 仍由 SQL 拒绝，原历史和 head 不变。
        with pytest.raises(sqlite3.IntegrityError):
            with store._connection:
                store._insert_event(store._connection, {**first, "event_index": 2, "payload": {"conflict": True}})
        assert store.event_count("a:b") == 1
    finally:
        store.close()
        oracle.close()
    reopened = CharacterAgentSessionStore(tmp_path)
    try:
        assert reopened.list_all_events() == {"a:b": [first], "a": [second]}
    finally:
        reopened.close()


@pytest.mark.parametrize("fail_upgrade", [False, True])
def test_schema_one_session_identity_upgrade_is_atomic(tmp_path, fail_upgrade):
    oracle = CharacterAgentSessionStore()
    first = oracle.append_event("a:b", "c", 1, {})
    second = oracle.append_event("a", "b:c", 1, {})
    path = tmp_path / "character_sessions.sqlite3"
    old_sql = "CREATE TABLE character_session_events (actor_id TEXT NOT NULL, event_index INTEGER NOT NULL CHECK(event_index>0), event_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(actor_id,event_index))"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE character_session_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        db.execute("INSERT INTO character_session_metadata VALUES ('schema_version','1')")
        db.execute(old_sql)
        db.execute("CREATE INDEX character_session_event_types ON character_session_events(actor_id,event_type,event_index)")
        db.execute("CREATE TABLE character_session_heads (actor_id TEXT PRIMARY KEY, event_count INTEGER NOT NULL CHECK(event_count>0), event_id TEXT NOT NULL)")
        db.execute("INSERT INTO character_session_events VALUES (?,?,?,?,?)", (first["actor_id"], 1, first["event_id"], first["event_type"], json.dumps(first)))
        db.execute("INSERT INTO character_session_heads VALUES (?,?,?)", (first["actor_id"], 1, first["event_id"]))
        if fail_upgrade:
            db.execute("CREATE TRIGGER fail_upgrade BEFORE UPDATE ON character_session_metadata BEGIN SELECT RAISE(ABORT,'upgrade blocked'); END")
    # 已有 SQL 库升级不能回头读取冻结的 legacy 备份。
    (tmp_path / "character_agent_session_store.json").write_text("{bad", encoding="utf-8")
    if fail_upgrade:
        with pytest.raises(sqlite3.IntegrityError, match="upgrade blocked"):
            CharacterAgentSessionStore(tmp_path)
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT value FROM character_session_metadata").fetchall() == [("1",)]
            assert db.execute("SELECT sql FROM sqlite_master WHERE name='character_session_events'").fetchone()[0] == old_sql
            assert json.loads(db.execute("SELECT payload_json FROM character_session_events").fetchone()[0]) == first
            assert db.execute("SELECT * FROM character_session_heads").fetchall() == [(first["actor_id"], 1, first["event_id"])]
            db.execute("DROP TRIGGER fail_upgrade")
    restored = CharacterAgentSessionStore(tmp_path)
    try:
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT value FROM character_session_metadata").fetchall() == [("2",)]
        restored._runtime_id = oracle._runtime_id
        assert restored.append_event("a", "b:c", 1, {}, expected_revision=0) == second
        assert restored.list_all_events() == {"a:b": [first], "a": [second]}
    finally:
        restored.close()
        oracle.close()
    reopened = CharacterAgentSessionStore(tmp_path)
    try:
        assert reopened.list_all_events() == {"a:b": [first], "a": [second]}
    finally:
        reopened.close()


@pytest.mark.parametrize("history", [1000, 10000])
def test_indexed_session_reopens_without_decoding_history(tmp_path, monkeypatch, history):
    store = CharacterAgentSessionStore(storage_root=tmp_path)
    events = [store.append_event("char_a", "perceived", i, {"i": i}) for i in range(history)]
    store.append_event("char_b", "settled", 1, {})
    store.close()
    original_loads = json.loads

    def no_history_decode(*args, **kwargs):
        raise AssertionError("normal ready must not decode historical events")

    with monkeypatch.context() as patch:
        patch.setattr(json, "loads", no_history_decode)
        reopened = CharacterAgentSessionStore(storage_root=tmp_path)
        assert reopened.event_count("char_a") == history
        assert reopened.actor_ids() == ("char_a", "char_b")
        assert reopened._events_by_actor == {}
    assert json.loads is original_loads
    assert reopened.read_event("char_a", event_index=500) == events[499]
    assert reopened.read_event("char_a", event_id=events[600]["event_id"]) == events[600]
    assert reopened.read_event("char_b", event_id=events[600]["event_id"]) is None
    assert reopened.read_events_page("char_a", after_index=995, through_index=999, limit=2) == events[995:997]
    assert reopened.list_events_after("char_a", 998) == events[998:]
    assert reopened.list_events("char_a") == events
    reopened.close()


def test_legacy_import_write_failure_rolls_back_schema_and_events(tmp_path, monkeypatch):
    events = [{"event_id": f"a:{i}", "event_index": i, "actor_id": "a", "event_type": "fact", "producer_ts": i, "payload": {}} for i in (1, 2)]
    legacy = tmp_path / "character_agent_session_store.json"
    legacy.write_text(json.dumps({"a": events}), encoding="utf-8")
    original = CharacterAgentSessionStore._insert_event

    def fail_second(db, entry):
        original(db, entry)
        if entry["event_index"] == 2:
            raise OSError("disk full")

    with monkeypatch.context() as patch:
        patch.setattr(CharacterAgentSessionStore, "_insert_event", staticmethod(fail_second))
        with pytest.raises(OSError, match="disk full"):
            CharacterAgentSessionStore(tmp_path)
    with sqlite3.connect(tmp_path / "character_sessions.sqlite3") as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'character_session_%'").fetchall() == []
    reopened = CharacterAgentSessionStore(tmp_path)
    assert reopened.list_events("a") == events
    reopened.close()
    with pytest.raises(RuntimeError, match="character_session_store_closed"):
        reopened.append_event("a", "closed", 3, {})


def test_session_transaction_rolls_back_event_if_head_write_fails(tmp_path):
    store = CharacterAgentSessionStore(database_path=tmp_path / "world.sqlite")
    first = store.append_event("char_a", "first", 1, {})
    with sqlite3.connect(tmp_path / "world.sqlite") as db:
        db.execute("CREATE TRIGGER fail_head BEFORE UPDATE ON character_session_heads BEGIN SELECT RAISE(ABORT, 'head failed'); END")
    with pytest.raises(sqlite3.IntegrityError, match="head failed"):
        store.append_event("char_a", "second", 2, {})
    assert store.list_events("char_a") == [first]
    assert store.event_count("char_a") == 1
    with sqlite3.connect(tmp_path / "world.sqlite") as db:
        db.execute("DROP TRIGGER fail_head")
    second = store.append_event("char_a", "second", 2, {}, expected_revision=1)
    assert second["event_index"] == 2
    store.close()


def test_independent_connections_share_durable_revision_and_do_not_reimport(tmp_path):
    archive = tmp_path / "legacy"
    archive.mkdir()
    database = tmp_path / "graph.sqlite"
    first = CharacterAgentSessionStore(archive, database_path=database)
    second = CharacterAgentSessionStore(archive, database_path=database)
    event = first.append_event("char_a", "first", 1, {})
    with pytest.raises(ValueError, match="character_revision_conflict"):
        second.append_event("char_a", "stale", 2, {}, expected_revision=0)
    second.append_event("char_a", "second", 2, {}, expected_revision=1)
    # 已迁移的旧文件不再是权威；正常启动不能读取损坏的冷备份。
    (archive / "character_agent_session_store.json").write_text("{bad", encoding="utf-8")
    first.close()
    second.close()
    reopened = CharacterAgentSessionStore(archive, database_path=database)
    assert reopened.event_count("char_a") == 2
    assert reopened.read_event("char_a", event_index=1) == event
    assert reopened.read_events_page("char_a", event_types=("second",), limit=1)[0]["event_index"] == 2
    reopened.close()


def test_failed_legacy_import_is_atomic_and_can_retry(tmp_path):
    legacy = tmp_path / "character_agent_session_store.json"
    event = {"event_id": "a:1", "event_index": 1, "actor_id": "a", "event_type": "fact", "producer_ts": 1, "payload": {}}
    legacy.write_text(json.dumps({"a": [event, {**event, "event_id": "a:3", "event_index": 3}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="session_event_index_gap"):
        CharacterAgentSessionStore(tmp_path)
    legacy.write_text(json.dumps({"a": [event]}), encoding="utf-8")
    reopened = CharacterAgentSessionStore(tmp_path)
    assert reopened.list_events("a") == [event]
    reopened.close()


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": -1}, {"after_index": -1}, {"after_index": True}, {"through_index": -1}])
def test_session_page_rejects_invalid_bounds(tmp_path, kwargs):
    store = CharacterAgentSessionStore(tmp_path)
    try:
        with pytest.raises(ValueError):
            store.read_events_page("char_a", **kwargs)
    finally:
        store.close()
