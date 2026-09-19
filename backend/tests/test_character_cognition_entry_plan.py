"""冻结 Siming 入站的 L1 after-state，不重放感知。"""
from copy import deepcopy

from app.character_agent.reasoning.l1_perception import CharacterAgentL1Service
from test_cognition_completion_revision import perceived, runtime, source_args


def test_siming_l1_plan_is_pure_and_matches_existing_apply_for_new_and_existing_actor():
    payload = source_args(None, 'ingest_siming_output')['payload'].model_dump(exclude_none=True)
    payload.update(target_actor_id='char_a', pressure_hint='uncertain', reason_scope='watch', salience_boost=.9)
    for existing in (False, True):
        l1 = CharacterAgentL1Service()
        if existing:
            l1.apply_character_perceived_event(perceived())
        before = deepcopy(l1._snapshots)
        planned = l1.plan_siming_output(payload)
        assert l1._snapshots == before
        actual = l1.apply_siming_output(payload)
        assert actual == planned
        planned.unresolved_signals.append('external mutation')
        assert 'external mutation' not in actual.unresolved_signals


def test_siming_entry_plan_freezes_supervision_tension_wake_and_l1_without_writes(tmp_path):
    from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime

    rt = CharacterAgentRuntime(storage_root=tmp_path)
    payload = source_args(None, 'ingest_siming_output')['payload'].model_dump(exclude_none=True)
    payload.update(pressure_hint='uncertain', reason_scope='watch', salience_boost=.99)
    before = rt._capture_cognition_pin('char_a')
    writes = rt._session_store._connection.total_changes
    plan = rt._plan_siming_entry(payload)
    assert rt._capture_cognition_pin('char_a') == before
    assert rt._session_store._connection.total_changes == writes
    assert rt.get_session_timeline('char_a') == []
    assert plan['actor_id'] == 'char_a'
    assert [event['event_type'] for event in plan['events']] == [
        'character_unresolved_tension_event', 'siming_output_event']
    assert plan['after']['supervision_state']['active_constraints']['pressure_theme'] == 'uncertain'
    assert plan['after']['wake_up']['wake_up_requested'] is True
    assert plan['after']['private_snapshot']['last_siming_catalyst']
    import json
    assert json.loads(json.dumps(plan)) == plan
    rt.close()


def test_siming_entry_plan_matches_actual_existing_prefix_before_first_provider():
    rt = runtime()
    payload = source_args(rt, 'ingest_siming_output')['payload'].model_dump(exclude_none=True)
    payload.update(pressure_hint='uncertain', reason_scope='watch', salience_boost=.99)
    plan = rt._plan_siming_entry(payload)
    advance = rt.prepare_cognition_job(source_kind='ingest_siming_output', payload=payload)
    assert advance.status == 'pending'
    assert rt._l2._gateway.requests == []
    actual_events = [{field: item[field] for field in ('event_type', 'producer_ts', 'payload')}
        for item in rt.get_session_timeline('char_a')]
    assert actual_events[:-1] == plan['events']
    import json
    assert actual_events[-1] == dict(event_type='l2_reasoning_request', producer_ts=300,
        payload=json.loads(advance.next_job.request_json))
    assert rt.get_private_snapshot('char_a').model_dump(mode='json') == plan['after']['private_snapshot']
    assert rt._supervision_states['char_a'].model_dump(mode='json') == plan['after']['supervision_state']
    assert rt._wake_up_signals['char_a'] == plan['after']['wake_up']
    rt.reset_cognition_jobs()
    rt.close()
