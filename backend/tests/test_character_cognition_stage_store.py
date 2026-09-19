"""Character 阶段事实与续接帧必须在原 session SQLite 内原子提交。"""
from copy import deepcopy

import pytest

from app.character_agent.storage.session_store import CharacterAgentSessionStore


def _store(path):
    store = CharacterAgentSessionStore(database_path=path)
    store.initialize_recovery()
    store.initialize_cognition_admissions()
    return store


def _plan():
    return dict(actor_id='char_a', key='dispatch:1/char_a/l2/0', expected_revision=0,
        events=[dict(event_type='dynamic_state_event', producer_ts=42,
            payload={'stress_load': .4, 'vigilance_level': .2, 'distraction_level': .1}),
            dict(event_type='goal_state_event', producer_ts=42, payload={'primary_goal': 'wait'})],
        before={'stage': 'l2', 'request': {'messages': []}},
        after={'stage': 'l3', 'interpretation': {'summary': 'wait'}})


def test_cognition_stage_reopen_replays_original_events_and_frame_without_writes(tmp_path):
    path = tmp_path / 'session.sqlite3'
    store = _store(path)
    plan = _plan()
    receipt = store.commit_cognition_stage(**plan)
    assert len(receipt['events']) == 2
    assert store.event_count('char_a') == 2
    assert store.read_runtime_state('char_a')['goal_history'][-1]['primary_goal'] == 'wait'
    store.close()
    restored = _store(path)
    writes = restored._connection.total_changes
    assert restored.commit_cognition_stage(**plan) == receipt
    assert restored._connection.total_changes == writes
    assert restored.list_events('char_a') == receipt['events']
    assert receipt['plan']['before'] == plan['before'] and receipt['plan']['after'] == plan['after']
    for field in ('events', 'before', 'after', 'expected_revision'):
        changed = deepcopy(plan)
        if field == 'events':
            changed[field][0]['payload']['stress_load'] = .9
        elif field == 'expected_revision':
            changed[field] = 2
        else:
            changed[field]['changed'] = True
        with pytest.raises(ValueError, match='cognition_stage_conflict'):
            restored.commit_cognition_stage(**changed)
    assert restored._connection.total_changes == writes
    restored.close()


def test_cognition_stage_receipt_failure_rolls_back_events_and_reducer(tmp_path, monkeypatch):
    store = _store(tmp_path / 'session.sqlite3')
    original = store.save_receipt

    def fail(*args, **kwargs):
        if kwargs['kind'] == 'cognition_stage':
            raise OSError('receipt disk failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(store, 'save_receipt', fail)
    with pytest.raises(OSError, match='receipt disk failure'):
        store.commit_cognition_stage(**_plan())
    assert store.event_count('char_a') == 0
    assert store.read_runtime_state('char_a') is None
    assert store.read_receipt('char_a', kind='cognition_stage', key=_plan()['key']) is None
    monkeypatch.setattr(store, 'save_receipt', original)
    assert len(store.commit_cognition_stage(**_plan())['events']) == 2
    store.close()


def test_cognition_stage_cas_rejects_without_partial_events(tmp_path):
    store = _store(tmp_path / 'session.sqlite3')
    store.append_event('char_a', 'goal_state_event', 41, {'primary_goal': 'prior'})
    writes = store._connection.total_changes
    with pytest.raises(ValueError, match='character_revision_conflict'):
        store.commit_cognition_stage(**_plan())
    assert store.event_count('char_a') == 1
    assert store._connection.total_changes == writes
    store.close()


def test_cognition_stage_hard_exit_keeps_atomic_events_and_frames(tmp_path):
    import json
    import os
    import subprocess
    import sys

    path = tmp_path / 'crash.sqlite3'
    plan = _plan()
    script = '''import json, os, sys
from app.character_agent.storage.session_store import CharacterAgentSessionStore
store = CharacterAgentSessionStore(database_path=sys.argv[1])
store.initialize_recovery()
store.initialize_cognition_admissions()
store.commit_cognition_stage(**json.loads(sys.argv[2]))
os._exit(0)
'''
    result = subprocess.run([sys.executable, '-c', script, str(path), json.dumps(plan)],
        env=os.environ.copy(), timeout=20, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    store = _store(path)
    receipt = store.read_receipt('char_a', kind='cognition_stage', key=plan['key'])
    writes = store._connection.total_changes
    assert store.commit_cognition_stage(**plan) == receipt
    assert store._connection.total_changes == writes
    assert store.list_events('char_a') == receipt['events']
    assert store.read_runtime_state('char_a')['event_index'] == 2
    store.close()


def test_plain_append_participates_in_existing_session_transaction(tmp_path):
    store = _store(tmp_path / 'session.sqlite3')
    with pytest.raises(OSError, match='stage failed'):
        with store.transaction():
            store.append_event('char_a', 'goal_state_event', 42, {'primary_goal': 'rollback'})
            raise OSError('stage failed')
    assert store.event_count('char_a') == 0
    assert store.read_runtime_state('char_a') is None
    store.close()
