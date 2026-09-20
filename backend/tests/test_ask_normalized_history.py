from copy import deepcopy
import sqlite3

import pytest

from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore
from app.character_agent.storage.session_store import CharacterAgentSessionStore


def incoming(index):
    return ActorSceneKnowledgeEntry(entry_id='ask:a:box', actor_id='a', session_id='s', scene_id='scene',
        subject_ref='box', knowledge_type='space', summary='same' if index % 2 == 0 else 'different',
        source_kind='interaction_failure', confidence=.9, source_refs=['', 'shared', f'source:{index}', 'shared'])


def open_store(path):
    persistence = CharacterAgentSessionStore(database_path=path)
    persistence.initialize_recovery()
    store = ActorSceneKnowledgeStore()
    store.bind_persistence(persistence)
    return persistence, store


def test_hot_ask_write_preserves_full_history_without_reading_it(tmp_path, monkeypatch):
    persistence, store = open_store(tmp_path / 'ask.db')
    expected = ActorSceneKnowledgeStore()
    def forbidden(**kwargs):
        raise AssertionError('hot write expanded full ASK history')
    monkeypatch.setattr(persistence, 'read_ask', forbidden)
    for index in range(240):
        value = incoming(index)
        expected.upsert(value, producer_ts=index // 2)
        store.record(value, producer_ts=index // 2)
    monkeypatch.undo()
    actual = store.entries_for_actor('a')[0].model_dump(mode='json')
    assert actual == expected.entries_for_actor('a')[0].model_dump(mode='json')
    assert store.trace == expected.trace
    # 来源前缀只存一次；历史仍完整可重建，不能只是换位置存展开JSON。
    payload_bytes = persistence._connection.execute('SELECT SUM(length(payload_json)) FROM character_session_ask').fetchone()[0]
    parts_bytes = persistence._connection.execute('SELECT SUM(length(payload_json)) FROM character_session_ask_parts').fetchone()[0]
    import json
    assert payload_bytes + parts_bytes < len(json.dumps(actual)) / 2
    persistence.close()
    reopened, restored = open_store(tmp_path / 'ask.db')
    assert restored.entries_for_actor('a')[0].model_dump(mode='json') == actual
    reopened.close()


def test_legacy_ask_migration_preserves_duplicate_order_and_resolution(tmp_path):
    path = tmp_path / 'old.db'
    persistence, store = open_store(path)
    for index in range(6):
        store.upsert(incoming(index), producer_ts=1)
    original = store.entries_for_actor('a')[0].model_dump(mode='json')
    original['conflicts'].append(deepcopy(original['conflicts'][0]))
    original['conflicts'][0]['resolved'] = True
    original['conflicts'][0]['resolved_by_ref'] = 'result:old'
    original['conflicts'][0]['source_refs'] = ['odd', '', 'odd']
    import json
    persistence._connection.execute('UPDATE character_session_ask SET payload_json=?', (json.dumps(original),))
    persistence._connection.execute("UPDATE character_session_metadata SET value='1' WHERE key='recovery_version'")
    persistence._connection.execute('DROP TABLE IF EXISTS character_session_ask_parts')
    persistence._connection.execute('DROP TABLE character_session_memory_summary')
    persistence._connection.commit()
    trace = store.trace
    persistence.close()
    reopened, restored = open_store(path)
    assert reopened._connection.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone()[0] == '3'
    assert restored.entries_for_actor('a')[0].model_dump(mode='json') == original
    assert restored.trace == trace
    reopened.close()


def test_lineage_string_membership_is_linear_and_preserves_old_duplicates():
    from app.models.object_anchor import append_unique_lineage
    class Counted(str):
        comparisons = 0
        __hash__ = str.__hash__
        def __eq__(self, other):
            type(self).comparisons += 1
            return super().__eq__(other)
    original = ['', 'old', 'old', *[Counted(f'source:{i}') for i in range(100)]]
    values = [Counted(f'source:{i}') for i in range(100)] + ['', 'new', 'new']
    result = append_unique_lineage(original, values)
    assert result == [*original, 'new']
    assert Counted.comparisons < 300


def test_selected_history_gap_is_rejected_but_reopen_does_not_scan_history(tmp_path):
    path = tmp_path / 'gap.db'
    persistence, store = open_store(path)
    for index in range(8):
        store.record(incoming(index), producer_ts=index)
    persistence._connection.execute("DELETE FROM character_session_ask_parts WHERE kind='conflicts' AND ordinal=1")
    persistence._connection.commit()
    persistence.close()
    reopened, restored = open_store(path)
    with pytest.raises(ValueError, match='ask_history_order_invalid'):
        restored.entries_for_actor('a')
    reopened.close()


def test_upgrade_failure_rolls_back_head_parts_and_version(tmp_path, monkeypatch):
    from app.character_agent.storage import ask_storage
    path = tmp_path / 'migration.db'
    persistence, store = open_store(path)
    store.upsert(incoming(0), producer_ts=1)
    original = store.entries_for_actor('a')[0].model_dump(mode='json')
    import json
    persistence._connection.execute('UPDATE character_session_ask SET payload_json=?', (json.dumps(original),))
    persistence._connection.execute("UPDATE character_session_metadata SET value='1' WHERE key='recovery_version'")
    persistence._connection.execute('DROP TABLE character_session_ask_parts')
    persistence._connection.execute('DROP TABLE character_session_memory_summary')
    persistence._connection.commit()
    persistence.close()
    write = ask_storage.write
    def fail_after_write(*args, **kwargs):
        write(*args, **kwargs)
        raise OSError('migration interrupted')
    with monkeypatch.context() as patch:
        patch.setattr(ask_storage, 'write', fail_after_write)
        with pytest.raises(OSError, match='migration interrupted'):
            open_store(path)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone()[0] == '1'
        assert not db.execute("SELECT name FROM sqlite_master WHERE name='character_session_ask_parts'").fetchall()
        assert json.loads(db.execute('SELECT payload_json FROM character_session_ask').fetchone()[0]) == original
    restored, store = open_store(path)
    assert store.entries_for_actor('a')[0].model_dump(mode='json') == original
    restored.close()


def test_hot_write_only_appends_history_and_backup_keeps_frozen_prefixes(tmp_path):
    persistence, store = open_store(tmp_path / 'source.db')
    store.record(incoming(0), producer_ts=0)
    statements = []
    persistence._connection.set_trace_callback(statements.append)
    for index in range(1, 10):
        store.record(incoming(index), producer_ts=index)
    persistence._connection.set_trace_callback(None)
    assert not any('DELETE' in text or ('SELECT ordinal' in text and ("'conflicts'" in text or "'revisions'" in text)) for text in statements)
    original = store.entries_for_actor('a')[0].model_dump(mode='json')
    with sqlite3.connect(tmp_path / 'backup.db') as backup:
        persistence._connection.backup(backup)
    persistence.close()
    reopened, restored = open_store(tmp_path / 'backup.db')
    assert restored.entries_for_actor('a')[0].model_dump(mode='json') == original
    # 新来源不会反向改变既有冲突内冻结的前缀。
    restored.record(incoming(12), producer_ts=12)
    assert restored.entries_for_actor('a')[0].model_dump(mode='json')['conflicts'] == original['conflicts']
    reopened.close()
