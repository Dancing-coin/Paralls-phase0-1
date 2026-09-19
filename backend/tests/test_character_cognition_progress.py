"""Character 阶段位置只是原 receipts 的持久索引，终态必须退出 pending。"""
import pytest

from test_character_cognition_admission import request, service


def _advance(admissions, key, revision, *, stage='entry', status='commit_started', **kwargs):
    if status == 'provider_pending':
        kwargs.setdefault('request_json', '{"task_kind":"' + stage + '"}')
    return admissions.advance_progress(key=key, expected_revision=revision, stage=stage, status=status,
        frame={'actor_id': 'char_a', 'stage': stage}, now=110., **kwargs)


def test_character_progress_reopen_cas_exact_retry_and_terminal_pending(tmp_path):
    path = tmp_path / 'session.sqlite3'
    store, admissions = service(path)
    child = admissions.admit(**request())
    plan = {'events': [], 'after': {'actor_id': 'char_a', 'stage': 'entry'}}
    initial = _advance(admissions, child.child_key, 0, plan=plan)
    assert initial.revision == 1 and initial.input_digest == child.input_digest
    store.close()
    store, admissions = service(path)
    assert admissions.read_progress(child.child_key) == initial
    writes = store._connection.total_changes
    assert _advance(admissions, child.child_key, 0, plan=plan) == initial
    assert store._connection.total_changes == writes
    with pytest.raises(ValueError, match='cognition_progress_conflict'):
        _advance(admissions, child.child_key, 0, plan={'events': ['changed']})
    ready = _advance(admissions, child.child_key, 1, status='stage_ready', plan=plan)
    pending = _advance(admissions, child.child_key, 2, stage='l2', status='provider_pending')
    result = _advance(admissions, child.child_key, 3, stage='l2', status='result_ready', completion={'output': {}})
    l2_plan = {'events': [], 'after': {'actor_id': 'char_a', 'stage': 'l2'}}
    committed = _advance(admissions, child.child_key, 4, stage='l2', plan=l2_plan)
    _advance(admissions, child.child_key, 5, stage='l2', status='stage_ready')
    _advance(admissions, child.child_key, 6, stage='l3', status='provider_pending')
    _advance(admissions, child.child_key, 7, stage='l3', status='result_ready', completion={'output': {}})
    _advance(admissions, child.child_key, 8, stage='l3', plan={'events': [], 'after': {'actor_id': 'char_a', 'stage': 'l3'}})
    terminal = _advance(admissions, child.child_key, 9, stage='l3', status='completed')
    assert [row.revision for row in (ready, pending, result, committed, terminal)] == [2, 3, 4, 5, 10]
    assert admissions.list_pending() == ()
    assert admissions.read(child.child_key) == child
    assert _advance(admissions, child.child_key, 0, plan=plan) == initial
    store.close()
    store, admissions = service(path)
    assert admissions.read_progress(child.child_key) == terminal
    assert admissions.list_pending() == ()
    store.close()


def test_character_progress_receipt_and_head_rollback_together(tmp_path):
    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    store._connection.execute("CREATE TRIGGER fail_progress BEFORE UPDATE ON character_session_cognition_heads BEGIN SELECT RAISE(ABORT,'progress_pointer_failure'); END")
    with pytest.raises(Exception, match='progress_pointer_failure'):
        _advance(admissions, child.child_key, 0, plan={'events': []})
    assert admissions.read_progress(child.child_key) is None
    assert store._connection.execute("SELECT count(*) FROM character_session_receipts WHERE kind='cognition_progress'").fetchone()[0] == 0
    assert admissions.list_pending() == (child,)
    store.close()


@pytest.mark.parametrize('status', ['provider_pending', 'result_ready', 'completed'])
def test_character_progress_cannot_skip_initial_commit(tmp_path, status):
    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    writes = store._connection.total_changes
    with pytest.raises(ValueError, match='cognition_progress_transition_invalid'):
        _advance(admissions, child.child_key, 0, status=status)
    assert store._connection.total_changes == writes
    store.close()


def test_expired_unstarted_child_can_only_become_stale_without_effects(tmp_path):
    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    with pytest.raises(ValueError, match='cognition_admission_expired'):
        admissions.advance_progress(key=child.child_key, expected_revision=0, stage='entry', status='commit_started',
            frame={'actor_id': 'char_a', 'stage': 'entry'}, now=201., plan={'events': []})
    stale = admissions.advance_progress(key=child.child_key, expected_revision=0, stage='entry', status='stale',
        frame={'actor_id': 'char_a', 'stage': 'entry'}, now=201., reason='expired')
    assert stale.status == 'stale' and admissions.list_pending() == ()
    assert store.event_count('char_a') == 0
    store.close()


def test_legacy_admission_pointer_migration_rolls_back_and_preserves_original_receipt(tmp_path):
    import sqlite3

    path = tmp_path / 'session.sqlite3'
    store, admissions = service(path)
    child = admissions.admit(**request())
    with store.transaction():
        store._connection.execute('DROP INDEX character_session_cognition_due')
        store._connection.execute('ALTER TABLE character_session_cognition_heads RENAME TO old_heads')
        store._connection.execute('CREATE TABLE character_session_cognition_heads(child_key TEXT PRIMARY KEY, actor_id TEXT NOT NULL, admitted_at REAL NOT NULL)')
        store._connection.execute('INSERT INTO character_session_cognition_heads SELECT child_key,actor_id,admitted_at FROM old_heads')
        store._connection.execute('DROP TABLE old_heads')
        store._connection.execute("UPDATE character_session_metadata SET value='1' WHERE key='cognition_admission_version'")
    store._connection.set_authorizer(lambda action, arg1, *rest:
        sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_INDEX and arg1 == 'character_session_cognition_due'
        else sqlite3.SQLITE_OK)
    with pytest.raises(sqlite3.DatabaseError):
        store.initialize_cognition_admissions()
    store._connection.set_authorizer(None)
    assert {row[1] for row in store._connection.execute('PRAGMA table_info(character_session_cognition_heads)')} == {
        'child_key', 'actor_id', 'admitted_at'}
    assert store._connection.execute("SELECT value FROM character_session_metadata WHERE key='cognition_admission_version'").fetchone()[0] == '1'
    store.close()
    store, admissions = service(path)
    assert admissions.read(child.child_key) == child
    assert admissions.read_progress(child.child_key) is None
    assert admissions.list_pending() == (child,)
    store.close()


def test_provider_progress_requires_frozen_request_and_rejects_replacement(tmp_path):
    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    plan = {'events': [], 'after': {'actor_id': 'char_a', 'stage': 'entry'}}
    _advance(admissions, child.child_key, 0, plan=plan)
    _advance(admissions, child.child_key, 1, status='stage_ready')
    with pytest.raises(ValueError, match='cognition_progress_request_required'):
        admissions.advance_progress(key=child.child_key, expected_revision=2, stage='l2', status='provider_pending',
            frame={'actor_id': 'char_a', 'stage': 'l2'}, now=110.)
    pending = _advance(admissions, child.child_key, 2, stage='l2', status='provider_pending')
    with pytest.raises(ValueError, match='cognition_progress_request_conflict'):
        admissions.advance_progress(key=child.child_key, expected_revision=3, stage='l2', status='result_ready',
            frame=pending.frame, request_json='{"different":true}', completion={'output': {}}, now=111.)
    assert admissions.read_progress(child.child_key) == pending
    store.close()


def test_accepted_stage_plan_after_frame_and_completion_cannot_be_replaced(tmp_path):
    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    plan = {'events': [], 'after': {'actor_id': 'char_a', 'stage': 'entry'}}
    _advance(admissions, child.child_key, 0, plan=plan)
    with pytest.raises(ValueError, match='cognition_progress_transition_invalid'):
        admissions.advance_progress(key=child.child_key, expected_revision=1, stage='entry', status='stage_ready',
            frame={'actor_id': 'char_a', 'stage': 'entry', 'changed': True}, now=110.)
    _advance(admissions, child.child_key, 1, status='stage_ready')
    _advance(admissions, child.child_key, 2, stage='l2', status='provider_pending')
    original = _advance(admissions, child.child_key, 3, stage='l2', status='result_ready', completion={'output': {'value': 1}})
    with pytest.raises(ValueError, match='cognition_progress_completion_conflict'):
        _advance(admissions, child.child_key, 4, stage='l2', completion={'output': {'value': 2}}, plan=plan)
    assert admissions.read_progress(child.child_key) == original
    store.close()


def test_stale_terminal_preserves_original_accepted_plan_and_frame(tmp_path):
    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    plan = {'events': [], 'after': {'actor_id': 'char_a', 'stage': 'entry'}}
    initial = _advance(admissions, child.child_key, 0, plan=plan)
    with pytest.raises(ValueError, match='cognition_progress_transition_invalid'):
        _advance(admissions, child.child_key, 1, status='stale', reason='source_revoked', plan={'replacement': True})
    stale = _advance(admissions, child.child_key, 1, status='stale', reason='source_revoked')
    assert stale.plan == initial.plan and stale.frame == initial.frame
    assert admissions.list_pending() == ()
    store.close()


def test_legacy_missing_business_tick_cannot_start_new_progress(tmp_path):
    import json
    from app.character_agent.services.cognition_admission import _digest

    store, admissions = service(tmp_path / 'session.sqlite3')
    child = admissions.admit(**request())
    raw = child.model_dump(mode='json')
    raw.pop('producer_ts')
    raw['input_digest'] = _digest({key: value for key, value in raw.items() if key not in {
        'schema_version', 'child_key', 'admitted_at', 'state', 'input_digest'}})
    with store.transaction():
        store._connection.execute("UPDATE character_session_receipts SET receipt_json=? WHERE kind='cognition_admission'", (json.dumps(raw),))
    assert admissions.read(child.child_key).producer_ts is None
    with pytest.raises(ValueError, match='cognition_admission_business_tick_required'):
        _advance(admissions, child.child_key, 0, plan={'events': []})
    assert _advance(admissions, child.child_key, 0, status='stale', reason='missing_business_tick').status == 'stale'
    assert store.event_count('char_a') == 0
    store.close()
