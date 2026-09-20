"""用实际 Character SQLite 回执验证离线账本，模型任务状态与完成事实分开。"""
import json

import pytest

from scripts.verification import population_mixed_cognition as proof
from test_character_cognition_coordinator import setup


def test_scheduled_jobs_require_the_original_session_event_and_atomic_group(tmp_path, monkeypatch):
    from test_scheduled_cognition_source import setup as scheduled_setup
    rt, source = scheduled_setup(tmp_path)
    monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_a'])
    try:
        event = rt._session_store.append_event('char_a', 'character_perceived_event', 123, {'summary': 'original'})
        child, = source.admit(source_actor='char_a', producer_ts=123, now=10.)
        target = tmp_path / 'scheduled.jsonl'
        changes = rt._session_store._connection.total_changes
        proof.export_character(rt._session_store._database_path, target)
        rows = [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
        assert rows[0]['scheduled_source']['event'] == event
        assert proof.verify_character(target)['jobs'][0]['child_key'] == child.child_key
        assert rt._session_store._connection.total_changes == changes
        for failure in ('missing', 'event', 'index', 'batch_digest', 'batch_missing_child', 'batch_unexported_child'):
            altered = json.loads(json.dumps(rows))
            value = altered[0]['scheduled_source']
            if failure == 'missing':
                del altered[0]['scheduled_source']
            elif failure == 'event':
                value['event']['payload'] = {'summary': 'forged'}
            elif failure == 'index':
                value['row'][1] += 1
            elif failure == 'batch_digest':
                value['batch']['source_digest'] = 'forged'
            elif failure == 'batch_missing_child':
                value['batch']['child_keys'] = []
            else:
                value['batch']['child_keys'].append('unexported')
            bad = tmp_path / 'bad-scheduled.jsonl'
            bad.write_text('\n'.join(json.dumps(row) for row in altered)+'\n', encoding='utf-8')
            with pytest.raises(ValueError, match='scheduled'):
                proof.verify_character(bad)
        rt._session_store._connection.execute('DELETE FROM character_session_events WHERE actor_id=? AND event_id=?',
            ('char_a', event['event_id']))
        rt._session_store._connection.commit()
        with pytest.raises(ValueError, match='scheduled'):
            proof.export_character(rt._session_store._database_path, tmp_path / 'missing-source.jsonl')
    finally:
        rt.close()


def test_original_character_stages_export_without_writes_and_reject_missing_proof(tmp_path):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    coordinator.accept_l2(child.child_key, activation=handle, now=113., output={'interpretation_type': 'observation'})
    database = rt._session_store._database_path
    changes = rt._session_store._connection.total_changes
    target = tmp_path / 'character.jsonl'
    proof.export_character(database, target)
    result = proof.verify_character(target)
    assert result['states'] == {'result_ready': 1} and result['completed'] == 0
    assert result['jobs'][0]['providers'][0]['request_sha256'] == proof.sha256(pending.request_json.encode()).hexdigest()
    assert rt._session_store._connection.total_changes == changes
    rows = [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
    changed = tmp_path / 'bad.jsonl'
    for failure in ('receipt_missing', 'event_changed', 'progress_gap', 'request_changed', 'index_changed'):
        values = json.loads(json.dumps(rows))
        if failure == 'receipt_missing':
            values = [row for row in values if row['type'] != 'character_stage']
        elif failure == 'event_changed':
            row = next(row for row in values if row['type'] == 'character_stage' and row['events'])
            row['events'][0]['payload'] = {'forged': True}
        elif failure == 'progress_gap':
            values = [row for row in values if row['type'] != 'character_progress' or row['progress']['revision'] != 2]
        elif failure == 'request_changed':
            row = next(row for row in values if row['type'] == 'character_progress' and row['progress']['status'] == 'result_ready')
            row['progress']['request_json'] += ' '
        else:
            values[0]['head'][4] = 0
        changed.write_text('\n'.join(json.dumps(row) for row in values)+'\n', encoding='utf-8')
        with pytest.raises(ValueError):
            proof.verify_character(changed)
    rt.close()


def test_completed_deferred_entry_still_requires_its_original_committed_events(tmp_path):
    from test_character_cognition_admission import request
    rt, admissions, coordinator, original, handle = setup(tmp_path)
    rt.set_runtime_cadence_policy(degraded_mode=True, cognition_interval_ms=1000)
    rt._last_cognition_tick_ms['char_a'] = 300
    payload = dict(original.payload, delivery_id='deferred:delivery', producer_ts=301, salience_boost=0.)
    child = admissions.admit(**{**request(), 'source_kind': 'ingest_siming_output', 'payload': payload,
        'delivery_id': payload['delivery_id'], 'producer_ts': 301})
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    completed = coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    assert completed.status == 'completed'
    target = tmp_path / 'character.jsonl'
    proof.export_character(rt._session_store._database_path, target)
    result = proof.verify_character(target)
    assert result['states'] == {'admitted': 1, 'completed': 1}
    assert result['completed'] == 1 and result['pending'] == 1
    # 已完成但原 effect 事件被删除，不能只信 pending 索引或 completed 标签。
    event = rt._session_store.read_receipt('char_a', kind='cognition_stage', key=child.child_key+'/entry')['events'][0]
    rt._session_store._connection.execute('DELETE FROM character_session_events WHERE actor_id=? AND event_id=?', ('char_a', event['event_id']))
    rt._session_store._connection.commit()
    with pytest.raises(ValueError, match='event_index'):
        proof.export_character(rt._session_store._database_path, tmp_path / 'corrupt.jsonl')
    rt.close()


@pytest.mark.parametrize('stage', ['l2', 'l3'])
def test_original_provider_failure_receipt_binds_the_failed_call_without_invented_output(tmp_path, stage):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    try:
        if stage == 'l3':
            rt.set_control_mode('char_a', 'player_priority_assisted')
        coordinator.begin_entry(child.child_key, activation=handle, now=110.)
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
        pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
        calls = []
        if stage == 'l3':
            coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})
            calls.append(dict(family='character', request_sha256=proof.sha256(pending.request_json.encode()).hexdigest(),
                output_sha256=proof._digest({}), error=None))
            coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
            coordinator.resume_l2(child.child_key, activation=handle, now=115.)
            pending = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
        coordinator.accept_provider_error(child.child_key, activation=handle, now=117., stage=stage, error=TimeoutError('deadline'))
        getattr(coordinator, 'freeze_'+stage)(child.child_key, activation=handle, now=118.)
        getattr(coordinator, 'resume_'+stage)(child.child_key, activation=handle, now=119.)
        if stage == 'l3':
            coordinator.prepare_suggestion(child.child_key, activation=handle, now=120.)
            assert coordinator.resume_suggestion(child.child_key, activation=handle, now=121.).status == 'completed'
        target = tmp_path / 'character.jsonl'
        proof.export_character(rt._session_store._database_path, target)
        jobs = proof.verify_character(target)['jobs']
        if stage == 'l3':
            assert jobs[0]['state'] == 'completed' and len(jobs[0]['providers']) == 2
        binding = next(row for row in jobs[0]['providers'] if row['stage'] == stage)
        assert binding['error'] == 'TimeoutError' and binding['output_sha256'] is None
        from scripts.verification.population_mixed_verification import verify_character_provider_calls
        call = dict(family='character', request_sha256=proof.sha256(pending.request_json.encode()).hexdigest(), error='TimeoutError')
        verify_character_provider_calls(jobs, [*calls, call])
        for wrong in (None, dict(call, error=None), dict(call, request_sha256='0'*64)):
            with pytest.raises(ValueError, match='provider'):
                verify_character_provider_calls(jobs, [*calls, *([wrong] if wrong else [])])
    finally:
        rt.close()


def test_scheduled_group_cannot_disappear_with_its_only_child(tmp_path, monkeypatch):
    from test_scheduled_cognition_source import setup as scheduled_setup
    rt, source = scheduled_setup(tmp_path)
    monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_a'])
    try:
        rt._session_store.append_event('char_a', 'character_perceived_event', 123, {})
        child, = source.admit(source_actor='char_a', producer_ts=123, now=10.)
        db = rt._session_store._connection
        db.execute('DELETE FROM character_session_cognition_heads WHERE child_key=?', (child.child_key,))
        db.execute("DELETE FROM character_session_receipts WHERE kind='cognition_admission' AND receipt_key=?", (child.child_key,))
        db.commit()
        target = tmp_path / 'missing-child.jsonl'
        proof.export_character(rt._session_store._database_path, target)
        with pytest.raises(ValueError, match='mixed_scheduled_group_incomplete'):
            proof.verify_character(target)
        rows = [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
        rows = [row for row in rows if row['type'] != 'scheduled_batch']
        target.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        with pytest.raises(ValueError, match='mixed_character_ledger_coverage_invalid'):
            proof.verify_character(target)
    finally: rt.close()


@pytest.mark.parametrize('failure', ['missing', 'changed', 'duplicate', 'actor', 'child', 'orphan', 'count'])
def test_exported_frame_proof_rejects_missing_foreign_changed_or_unbound_bodies(tmp_path, failure):
    from test_character_cognition_frame import prepare
    rt, _, _, _, _, _ = prepare(tmp_path)
    try:
        target = tmp_path / 'frames.jsonl'
        proof.export_character(rt._session_store._database_path, target)
        assert proof.verify_character(target)['states'] == {'provider_pending': 1}
        rows = [json.loads(line) for line in target.read_text(encoding='utf-8').splitlines()]
        frame = next(row for row in rows if row['type'] == 'character_frame')
        if failure == 'missing':
            rows.remove(frame)
        elif failure == 'changed':
            body = json.loads(frame['receipt_json'])
            body['value']['control_mode'] = 'forged'
            frame['receipt_json'] = json.dumps(body)
        elif failure == 'duplicate':
            rows.insert(rows.index(frame), dict(frame))
        elif failure in {'actor', 'child'}:
            body = json.loads(frame['receipt_json'])
            body['actor_id' if failure == 'actor' else 'child_key'] = 'foreign'
            frame['receipt_json'] = json.dumps(body)
        elif failure == 'orphan':
            body = json.loads(frame['receipt_json'])
            body.update(origin_stage='suggestion', field='suggestion_context')
            rows.insert(rows.index(frame), dict(frame, key=proof.frame_key(body), receipt_json=json.dumps(body)))
        else:
            rows[-1]['frames'] += 1
        target.write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        with pytest.raises(ValueError, match='frame|coverage'):
            proof.verify_character(target)
    finally:
        rt.close()
