"""已完成的 ASK 投影读取不能竞争无关 SQLite 写者。"""
import sqlite3

import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime


@pytest.mark.parametrize('completed', [True, False])
def test_ask_projection_only_acquires_writer_when_cursor_needs_advancing(tmp_path, completed):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    session = runtime._session_store
    append = runtime._append_session_event if completed else session.append_event
    event = append('char_a', 'probe', 1, {})
    session._connection.execute('PRAGMA busy_timeout=0')
    blocker = sqlite3.connect(tmp_path / 'character_sessions.sqlite3')
    try:
        blocker.execute('BEGIN IMMEDIATE')
        if completed:
            runtime._update_memory_scene_knowledge(event)
            assert session.projection_cursor('char_a', 'ask') == event['event_index']
        else:
            with pytest.raises(sqlite3.OperationalError, match='locked'):
                runtime._update_memory_scene_knowledge(event)
            assert session.projection_cursor('char_a', 'ask') == 0
        assert session.event_count('char_a') == 1
        blocker.rollback()
        runtime._update_memory_scene_knowledge(event)
        assert session.projection_cursor('char_a', 'ask') == event['event_index']
    finally:
        blocker.rollback()
        blocker.close()
        runtime.close()


def test_completed_ask_projection_still_rejects_a_closed_session(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    event = runtime._append_session_event('char_a', 'probe', 1, {})
    runtime.close()
    with pytest.raises(RuntimeError, match='character_session_store_closed'):
        runtime._update_memory_scene_knowledge(event)
