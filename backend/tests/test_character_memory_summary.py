import json
import sqlite3

import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.storage import memory_summary
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore


def _events():
    for index in range(24):
        yield "character_perceived_event", {
            "summary": f"观察{index}", "target_object_id": f"obj:{index % 3}",
            "percept_channel": "visual", "certainty_score": .8,
            "fact_claim": {"scope_ref": "room:one", "subject_ref": "obj:claim", "predicate": "state",
                           "value": str(index % 2), "valid_at": index, "source_ref": f"source:{index}"},
        }
        yield "character_agent_settlement_result", {"result_type": "constraint_state_result", "constraint_summary": f"约束{index % 3}"}
        yield "relational_belief_event", {"entity_id": "char_b", "belief_type": "trust_level", "value": "guarded" if index % 2 else "trusting"}
        yield "knowledge_belief_event", {"proposition_key": "weather", "proposition": str(index), "state": "suspected"}
        yield "higher_order_belief_event", {"subject_actor_id": "char_b", "proposition_key": "weather", "meta_belief": f"belief:{index}"}
        yield "character_agent_dialogue_response", {"content": f"对话{index}"}
    # 过期 claim 不可覆盖较新命题，即使它进入了事件记忆。
    yield "character_perceived_event", {"summary": "过期观察", "fact_claim": {
        "scope_ref": "room:one", "subject_ref": "obj:claim", "predicate": "state",
        "value": "stale", "valid_at": 0, "source_ref": "source:old"}}


def test_incremental_summary_matches_complete_replay_and_reopen(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    oracle = CharacterAgentMemoryStore()
    try:
        for index, (kind, payload) in enumerate(_events(), 1):
            event = runtime._append_session_event("char_a", kind, index, payload)
            oracle.write_event(event)
            assert runtime._session_store.read_memory_summary("char_a") == memory_summary.bundle_summary(oracle.retrieval_record_bundle("char_a"))
        expected = runtime._session_store.read_memory_summary("char_a")
        assert "观察0" in expected and "观察23" in expected and "belief:23" in expected
    finally:
        runtime.close()
    from app.character_agent.storage.session_store import CharacterAgentSessionStore
    monkeypatch.setattr(CharacterAgentSessionStore, "list_events", lambda *a, **k: pytest.fail("normal reopen scanned history"))
    reopened = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        assert reopened._memory_store.debug_memory_summary("char_a") == expected
        assert reopened._memory_store._events_by_actor == {}
    finally:
        reopened.close()


def _downgrade_summary(path):
    with sqlite3.connect(path / "character_sessions.sqlite3") as db:
        db.execute("DROP TABLE character_session_memory_summary")
        db.execute("UPDATE character_session_metadata SET value='2' WHERE key='recovery_version'")


def test_old_schema_summary_migration_preserves_history_and_is_atomic(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    for index, (kind, payload) in enumerate(_events(), 1):
        runtime._append_session_event("char_a", kind, index, payload)
    expected = runtime._session_store.read_memory_summary("char_a")
    timeline = runtime.get_session_timeline("char_a")
    runtime.close()
    _downgrade_summary(tmp_path)
    original = memory_summary.project
    def cut(db, event):
        original(db, event)
        if event["event_index"] == 5:
            raise OSError("summary migration cut")
    with monkeypatch.context() as guard:
        guard.setattr(memory_summary, "project", cut)
        with pytest.raises(OSError, match="summary migration cut"):
            CharacterAgentRuntime(storage_root=tmp_path)
    with sqlite3.connect(tmp_path / "character_sessions.sqlite3") as db:
        assert db.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone()[0] == "2"
        assert db.execute("SELECT name FROM sqlite_master WHERE name='character_session_memory_summary'").fetchone() is None
        assert [json.loads(row[0]) for row in db.execute("SELECT payload_json FROM character_session_events ORDER BY event_index")] == timeline
    reopened = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        assert reopened._session_store.read_memory_summary("char_a") == expected
        assert reopened.get_session_timeline("char_a") == timeline
    finally:
        reopened.close()


def test_summary_failure_rolls_back_event_and_runtime_state(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        runtime.record_dialogue_response(actor_id="char_a", producer_ts=1, payload={"content": "before"})
        store = runtime._session_store
        before = store.read_runtime_state("char_a")
        timeline = store.list_events("char_a")
        summary = store.read_memory_summary("char_a")
        store._connection.execute("CREATE TRIGGER reject_summary BEFORE INSERT ON character_session_memory_summary BEGIN SELECT RAISE(ABORT,'summary cut'); END")
        with pytest.raises(sqlite3.IntegrityError, match="summary cut"):
            runtime._append_session_event("char_a", "character_agent_dialogue_response", 2, {"content": "after"})
        assert store.read_runtime_state("char_a") == before
        assert store.list_events("char_a") == timeline
        assert store.read_memory_summary("char_a") == summary
    finally:
        runtime.close()


def test_current_schema_missing_summary_table_fails_closed(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    runtime.close()
    with sqlite3.connect(tmp_path / "character_sessions.sqlite3") as db:
        db.execute("DROP TABLE character_session_memory_summary")
    with pytest.raises(ValueError, match="schema_unsupported"):
        CharacterAgentRuntime(storage_root=tmp_path)
