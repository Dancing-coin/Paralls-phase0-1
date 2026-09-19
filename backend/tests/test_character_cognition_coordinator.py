"""真实子入站的第一阶段恢复，不能重新执行 Siming 感知入口。"""
import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from test_character_agent_activation_handoff import active_dialogue_decision
from test_character_cognition_admission import request
from test_cognition_completion_revision import source_args


def setup(root):
    from app.character_agent.services.cognition_coordinator import CharacterCognitionCoordinator
    rt = CharacterAgentRuntime(storage_root=root)
    rt.set_activation_authority(ProfileActivationAuthority(registry=rt._profile_registry, store=GameplayEventStore()))
    admissions = CharacterCognitionAdmissionService(store=rt._session_store, assert_owner=rt._assert_cognition_owner,
        validate_source=lambda _: None, activation_is_current=rt.activation_is_current)
    payload = source_args(rt, 'ingest_siming_output')['payload'].model_dump(mode='json')
    payload.update(pressure_hint='uncertain', salience_boost=.99)
    child = admissions.admit(**{**request(), 'source_kind': 'ingest_siming_output', 'payload': payload,
        'delivery_id': payload['delivery_id'], 'producer_ts': payload['producer_ts']})
    handle, receipt = rt.begin_actor_activation('char_a', active_dialogue_decision(), producer_ts=300)
    assert receipt.committed
    return rt, admissions, CharacterCognitionCoordinator(runtime=rt, admissions=admissions), child, handle


@pytest.mark.parametrize('reopen', [False, True])
def test_entry_commit_and_reopen_preserve_original_prefix_and_frozen_after(tmp_path, monkeypatch, reopen):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    expected = rt._plan_siming_entry(child.payload)
    started = coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    assert started.status == 'commit_started'
    assert rt.get_session_timeline('char_a') == []
    original = admissions.advance_progress
    def fail_ready(**kwargs):
        if kwargs['status'] == 'stage_ready':
            raise OSError('after effect before progress')
        return original(**kwargs)
    monkeypatch.setattr(admissions, 'advance_progress', fail_ready)
    with pytest.raises(OSError, match='after effect'):
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    saved = rt.get_session_timeline('char_a')
    assert [{key: row[key] for key in ('event_type', 'producer_ts', 'payload')} for row in saved] == expected['events']
    if reopen:
        rt.close()
        rt, admissions, coordinator, child, handle = setup(tmp_path)
    else:
        monkeypatch.setattr(admissions, 'advance_progress', original)
    monkeypatch.setattr(rt, '_plan_siming_entry', lambda *_: pytest.fail('must not replan'))
    monkeypatch.setattr(rt._l1, 'apply_siming_output', lambda *_: pytest.fail('must not replay perception'))
    ready = coordinator.resume_entry(child.child_key, activation=handle, now=112.)
    assert ready.status == 'stage_ready' and ready.frame == started.plan['after']
    assert rt.get_session_timeline('char_a') == saved
    assert rt.get_private_snapshot('char_a').model_dump(mode='json') == expected['after']['private_snapshot']
    assert rt._supervision_states['char_a'].model_dump(mode='json') == expected['after']['supervision_state']
    assert rt._wake_up_signals['char_a'] == expected['after']['wake_up']
    assert len(rt.get_unresolved_tensions('char_a')) == 1
    writes = rt._session_store._connection.total_changes
    assert coordinator.resume_entry(child.child_key, activation=handle, now=113.) == ready
    assert rt._session_store._connection.total_changes == writes
    rt.close()


def test_entry_requires_current_activation_and_source_before_any_stage_write(tmp_path):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    writes = rt._session_store._connection.total_changes
    with pytest.raises(ValueError, match='activation_invalid'):
        coordinator.begin_entry(child.child_key, activation=None, now=110.)
    assert admissions.read_progress(child.child_key) is None
    admissions._validate_source = lambda _: (_ for _ in ()).throw(ValueError('source_revoked'))
    with pytest.raises(ValueError, match='source_revoked'):
        coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    assert rt._session_store._connection.total_changes == writes
    rt.close()

@pytest.mark.parametrize('failure', ['expired', 'source', 'revision'])
def test_entry_resume_rejects_new_effects_on_expiry_revocation_or_original_cas_conflict(tmp_path, failure):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    if failure == 'source':
        admissions._validate_source = lambda _: (_ for _ in ()).throw(ValueError('source_revoked'))
    if failure == 'revision':
        rt._append_session_event('char_a', 'external_observation', 301, {'summary': 'later fact'})
    before = rt.get_session_timeline('char_a')
    pin = rt._capture_cognition_pin('char_a')
    with pytest.raises(ValueError):
        coordinator.resume_entry(child.child_key, activation=handle, now=201. if failure == 'expired' else 111.)
    assert rt.get_session_timeline('char_a') == before
    assert rt._capture_cognition_pin('char_a') == pin
    assert admissions.read_progress(child.child_key).status == 'commit_started'
    rt.close()


def test_entry_existing_effect_cannot_install_old_after_over_later_session_head(tmp_path, monkeypatch):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    started = coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    plan = started.plan
    rt._session_store.commit_cognition_stage(actor_id='char_a', key=f'{child.child_key}/entry',
        expected_revision=plan['expected_revision'], events=plan['events'], before=plan['before'], after=plan['after'])
    rt._finish_session_projections('char_a')
    rt._append_session_event('char_a', 'external_observation', 301, {'summary': 'later fact'})
    monkeypatch.setattr(rt, '_install_cognition_entry_after', lambda *_: pytest.fail('must not rewind after state'))
    with pytest.raises(ValueError, match='cognition_stage_head_changed'):
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    rt.close()

@pytest.mark.parametrize('effect_exists', [False, True])
def test_entry_never_overwrites_background_change_even_with_original_effect_receipt(tmp_path, effect_exists):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    started = coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    if effect_exists:
        plan = started.plan
        rt._session_store.commit_cognition_stage(actor_id='char_a', key=f'{child.child_key}/entry',
            expected_revision=plan['expected_revision'], events=plan['events'], before=plan['before'], after=plan['after'])
        rt._finish_session_projections('char_a')
    rt.set_background_mode('char_a', 'off')
    assert rt.activation_is_current(handle.lock_ref, handle.token)
    before = rt.get_session_timeline('char_a')
    with pytest.raises(ValueError, match='cognition_entry_stale_pin'):
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    assert rt.get_background_mode('char_a') == 'off'
    assert rt.get_session_timeline('char_a') == before
    rt.close()


def test_second_entry_restores_frozen_after_from_original_stage_receipt_on_startup(tmp_path, monkeypatch):
    rt, admissions, coordinator, first, handle = setup(tmp_path)
    coordinator.begin_entry(first.child_key, activation=handle, now=110.)
    coordinator.resume_entry(first.child_key, activation=handle, now=111.)
    payload = dict(first.payload, delivery_id='second:delivery', message_id='second:message', producer_ts=301)
    second = admissions.admit(**{**request(), 'source_kind': 'ingest_siming_output', 'payload': payload,
        'delivery_id': payload['delivery_id'], 'producer_ts': 301})
    started = coordinator.begin_entry(second.child_key, activation=handle, now=112.)
    original = admissions.advance_progress
    def fail_ready(**kwargs):
        if kwargs['status'] == 'stage_ready':
            raise OSError('second entry after effect')
        return original(**kwargs)
    monkeypatch.setattr(admissions, 'advance_progress', fail_ready)
    with pytest.raises(OSError, match='second entry'):
        coordinator.resume_entry(second.child_key, activation=handle, now=113.)
    events = rt.get_session_timeline('char_a')
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    ready = coordinator.resume_entry(second.child_key, activation=handle, now=114.)
    assert ready.frame == started.plan['after'] and ready.status == 'stage_ready'
    assert rt.get_session_timeline('char_a') == events
    assert rt.get_private_snapshot('char_a').model_dump(mode='json') == started.plan['after']['entry_after']['private_snapshot']
    rt.close()


def test_live_missing_l1_is_not_treated_as_startup_restore_permission(tmp_path):
    rt, admissions, coordinator, first, handle = setup(tmp_path)
    coordinator.begin_entry(first.child_key, activation=handle, now=110.)
    coordinator.resume_entry(first.child_key, activation=handle, now=111.)
    payload = dict(first.payload, delivery_id='second:delivery', message_id='second:message', producer_ts=301)
    second = admissions.admit(**{**request(), 'source_kind': 'ingest_siming_output', 'payload': payload,
        'delivery_id': payload['delivery_id'], 'producer_ts': 301})
    started = coordinator.begin_entry(second.child_key, activation=handle, now=112.)
    plan = started.plan
    rt._session_store.commit_cognition_stage(actor_id='char_a', key=f'{second.child_key}/entry',
        expected_revision=plan['expected_revision'], events=plan['events'], before=plan['before'], after=plan['after'])
    rt._finish_session_projections('char_a')
    rt._l1._snapshots.pop('char_a')
    with pytest.raises(ValueError, match='cognition_entry_stale_pin'):
        coordinator.resume_entry(second.child_key, activation=handle, now=113.)
    assert rt.get_private_snapshot('char_a') is None
    rt.close()


def test_l2_request_is_durable_before_dispatch_and_reopens_without_repreparing(tmp_path, monkeypatch):
    import json
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    assert pending.stage == 'l2' and pending.status == 'provider_pending'
    log = rt.get_session_timeline('char_a')[-1]
    assert log['event_type'] == 'l2_reasoning_request' and log['payload'] == json.loads(pending.request_json)
    saved = rt.get_session_timeline('char_a')
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    monkeypatch.setattr(rt._l2, 'prepare_siming_output', lambda *_args, **_kwargs: pytest.fail('must not prepare frozen request again'))
    again = coordinator.prepare_l2(child.child_key, activation=handle, now=113.)
    assert again == pending and rt.get_session_timeline('char_a') == saved
    accepted = coordinator.accept_l2(child.child_key, activation=handle, now=114., output={'interpretation_type': 'observation'})
    assert accepted.status == 'result_ready'
    assert accepted.request_json == pending.request_json
    writes = rt._session_store._connection.total_changes
    assert coordinator.accept_l2(child.child_key, activation=handle, now=115., output={'interpretation_type': 'observation'}) == accepted
    assert rt._session_store._connection.total_changes == writes
    rt.close()


def test_l2_request_and_pending_rollback_allow_retry_without_partial_log(tmp_path):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    ready = coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    before = rt.get_session_timeline('char_a')
    rt._session_store._connection.execute("CREATE TRIGGER reject_pending BEFORE UPDATE ON character_session_cognition_heads BEGIN SELECT RAISE(ABORT,'provider_pending_failure'); END")
    with pytest.raises(Exception, match='provider_pending_failure'):
        coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    assert rt.get_session_timeline('char_a') == before
    assert admissions.read_progress(child.child_key) == ready
    assert rt._session_store.read_receipt('char_a', kind='cognition_stage', key=f'{child.child_key}/l2/request') is None
    rt._session_store._connection.execute('DROP TRIGGER reject_pending')
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=113.)
    assert pending.status == 'provider_pending' and len(rt.get_session_timeline('char_a')) == len(before) + 1
    rt.close()


@pytest.mark.parametrize('changed_actor', ['char_a', 'char_b'])
def test_l2_completion_keeps_actor_local_strict_pins(tmp_path, changed_actor):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    rt.set_background_mode(changed_actor, 'off')
    writes = rt._session_store._connection.total_changes
    if changed_actor == 'char_a':
        with pytest.raises(ValueError, match='cognition_provider_stale_pin'):
            coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})
        assert admissions.read_progress(child.child_key) == pending
        assert rt._session_store._connection.total_changes == writes
    else:
        assert coordinator.accept_l2(child.child_key, activation=handle, now=113., output={}).status == 'result_ready'
    rt.close()


def test_durable_siming_entry_preserves_degraded_cadence_without_starting_l2(tmp_path):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    rt.set_runtime_cadence_policy(degraded_mode=True, cognition_interval_ms=1000)
    rt._last_cognition_tick_ms['char_a'] = 300
    payload = dict(child.payload, delivery_id='deferred:delivery', producer_ts=301, salience_boost=0.)
    child = admissions.admit(**{**request(), 'source_kind': 'ingest_siming_output', 'payload': payload,
        'delivery_id': payload['delivery_id'], 'producer_ts': 301})
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    completed = coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    assert completed.status == 'completed' and completed.frame['cadence']['deferred'] is True
    assert rt._last_cognition_tick_ms['char_a'] == 300
    assert all(row['event_type'] != 'l2_reasoning_request' for row in rt.get_session_timeline('char_a'))
    from test_cognition_completion_revision import runtime
    sync = runtime()
    sync.set_runtime_cadence_policy(degraded_mode=True, cognition_interval_ms=1000)
    sync._last_cognition_tick_ms['char_a'] = 300
    advance = sync.prepare_cognition_job(source_kind='ingest_siming_output', payload=payload)
    assert advance.status == 'completed' and advance.result == []
    assert [row['event_type'] for row in sync.get_session_timeline('char_a')] == [row['event_type'] for row in rt.get_session_timeline('char_a')]
    sync.close()
    rt.close()


def test_l2_effect_plan_and_apply_reopen_without_repeating_cognition_events(tmp_path, monkeypatch):
    from test_character_agent_cognition_writeback import _PositiveAffectStubL2
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})
    interpretation = _PositiveAffectStubL2().map_reasoning_output(actor_id='char_a', output={})
    monkeypatch.setattr(rt._l2, 'map_reasoning_output', lambda **_: interpretation)
    before = rt.get_session_timeline('char_a')
    planned = coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
    assert planned.status == 'commit_started' and rt.get_session_timeline('char_a') == before
    assert [event['event_type'] for event in planned.plan['events']] == [
        'knowledge_belief_event', 'social_cognition_event', 'higher_order_belief_event',
        'dynamic_state_event', 'character_interpretation_event']
    original = admissions.advance_progress
    def fail_ready(**kwargs):
        if kwargs['stage'] == 'l2' and kwargs['status'] == 'stage_ready':
            raise OSError('after cognition effect')
        return original(**kwargs)
    monkeypatch.setattr(admissions, 'advance_progress', fail_ready)
    with pytest.raises(OSError, match='after cognition effect'):
        coordinator.resume_l2(child.child_key, activation=handle, now=115.)
    assert rt.get_dynamic_state_record('char_a').storage_dump()['affect_state']['trust'] == .6
    saved = rt.get_session_timeline('char_a')
    assert len(saved) == len(before) + 5
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    monkeypatch.setattr(rt._l2, 'map_reasoning_output', lambda **_: pytest.fail('must not remap accepted result'))
    ready = coordinator.resume_l2(child.child_key, activation=handle, now=116.)
    assert ready.status == 'stage_ready' and ready.frame == planned.plan['after']
    assert rt.get_session_timeline('char_a') == saved
    assert rt.get_dynamic_state_record('char_a').storage_dump()['affect_state']['trust'] == .6
    assert rt.get_goal_state_history('char_a') == []
    rt.close()


def test_l3_request_preserves_initial_context_and_reopens_without_prepare(tmp_path, monkeypatch):
    from app.character_agent.planning.l3_planner import PreparedCharacterIntentPlan
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    l2 = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    output = rt._l2._gateway.complete_prepared_request(l2.request_json.encode())
    coordinator.accept_l2(child.child_key, activation=handle, now=113., output=output)
    coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
    ready = coordinator.resume_l2(child.child_key, activation=handle, now=115.)
    saved = rt.get_session_timeline('char_a')
    pending = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
    prepared = PreparedCharacterIntentPlan.from_json_value(pending.frame['l3_prepared'])
    assert prepared.request_json.decode() == pending.request_json
    assert pending.frame['context'] == ready.frame['context']
    assert rt._l3._consumed_behavior_policy_ids == set()
    assert rt.get_session_timeline('char_a') == saved
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    monkeypatch.setattr(rt._l3, 'prepare_intent_plan', lambda **_: pytest.fail('must not prepare L3 again'))
    assert coordinator.prepare_l3(child.child_key, activation=handle, now=117.) == pending
    assert rt.get_session_timeline('char_a') == saved
    rt.close()


def test_l3_pending_rejects_consumed_original_policy(tmp_path, monkeypatch):
    from app.character_agent.planning.l3_planner import PreparedCharacterIntentPlan
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    rt._session_append_event(actor_id='char_a', event_type='character_policy_candidate_event', producer_ts=1,
        payload={'status': 'candidate_only', 'candidate_id': 'pending-policy',
            'policy_type': 'recovery_policy', 'failed_intent': 'approach'})
    # 使用原完整 memory API 的真实候选，固定在 L2 初始 context 内进入 L3。
    monkeypatch.setattr(rt, 'get_memory_record_bundle', rt.get_memory_bundle)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    l2 = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    coordinator.accept_l2(child.child_key, activation=handle, now=113.,
        output=rt._l2._gateway.complete_prepared_request(l2.request_json.encode()))
    coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
    coordinator.resume_l2(child.child_key, activation=handle, now=115.)
    pending = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
    prepared = PreparedCharacterIntentPlan.from_json_value(pending.frame['l3_prepared'])
    assert prepared.behavior_policy['candidate_id'] == 'pending-policy'
    rt._l3.finish_intent_plan(prepared, rt._l3._gateway.complete_prepared_request(prepared.request_json))
    writes = rt._session_store._connection.total_changes
    with pytest.raises(ValueError, match='cognition_provider_stale_pin'):
        coordinator.prepare_l3(child.child_key, activation=handle, now=117.)
    assert rt._session_store._connection.total_changes == writes
    assert admissions.read_progress(child.child_key) == pending
    rt.close()


@pytest.mark.parametrize('with_policy', [False, True])
def test_l3_goal_plan_applies_once_after_reopen(tmp_path, monkeypatch, with_policy):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    if with_policy:
        rt._session_append_event(actor_id='char_a', event_type='character_policy_candidate_event', producer_ts=1,
            payload={'status': 'candidate_only', 'candidate_id': 'committed-policy',
                'policy_type': 'recovery_policy', 'failed_intent': 'approach'})
        monkeypatch.setattr(rt, 'get_memory_record_bundle', rt.get_memory_bundle)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    l2 = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    coordinator.accept_l2(child.child_key, activation=handle, now=113.,
        output=rt._l2._gateway.complete_prepared_request(l2.request_json.encode()))
    coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
    coordinator.resume_l2(child.child_key, activation=handle, now=115.)
    l3 = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
    coordinator.accept_l3(child.child_key, activation=handle, now=117.,
        output=rt._l3._gateway.complete_prepared_request(l3.request_json.encode()))
    before = rt.get_session_timeline('char_a')
    planned = coordinator.freeze_l3(child.child_key, activation=handle, now=118.)
    assert rt.get_session_timeline('char_a') == before
    assert [row['event_type'] for row in planned.plan['events']] == ['goal_state_event']
    assert rt._l3._consumed_behavior_policy_ids == set()
    original = admissions.advance_progress
    def fail_ready(**kwargs):
        if kwargs['stage'] == 'l3' and kwargs['status'] == 'stage_ready':
            raise OSError('after goal effect')
        return original(**kwargs)
    monkeypatch.setattr(admissions, 'advance_progress', fail_ready)
    with pytest.raises(OSError, match='after goal effect'):
        coordinator.resume_l3(child.child_key, activation=handle, now=119.)
    saved = rt.get_session_timeline('char_a')
    goal = rt.get_goal_state('char_a')
    assert len(saved) == len(before) + 1 and len(rt.get_goal_state_history('char_a')) == 1
    assert rt._l3._consumed_behavior_policy_ids == ({'committed-policy'} if with_policy else set())
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    assert rt._l3._consumed_behavior_policy_ids == ({'committed-policy'} if with_policy else set())
    monkeypatch.setattr(rt._l3, 'plan_intent_completion', lambda *_: pytest.fail('must not replan accepted L3'))
    ready = coordinator.resume_l3(child.child_key, activation=handle, now=120.)
    assert ready.status == 'stage_ready' and ready.frame == planned.plan['after']
    assert rt.get_session_timeline('char_a') == saved and rt.get_goal_state('char_a') == goal
    assert len(rt.get_goal_state_history('char_a')) == 1
    rt.close()


@pytest.mark.parametrize('with_policy', [False, True])
def test_assisted_persists_third_model_request_and_original_suggestion(tmp_path, monkeypatch, with_policy):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    rt.set_control_mode('char_a', 'player_priority_assisted')
    if with_policy:
        rt._session_append_event(actor_id='char_a', event_type='character_policy_candidate_event', producer_ts=1,
            payload={'status': 'candidate_only', 'candidate_id': 'assisted-policy',
                'policy_type': 'recovery_policy', 'failed_intent': 'approach'})
        monkeypatch.setattr(rt, 'get_memory_record_bundle', rt.get_memory_bundle)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    calls = []
    for stage in ('l2', 'l3'):
        pending = getattr(coordinator, 'prepare_'+stage)(child.child_key, activation=handle, now=112.)
        output = rt._l2._gateway.complete_prepared_request(pending.request_json.encode())
        if stage == 'l3':
            # 本例验证成功模型的第三请求；本地gateway默认floor应走单独降级用例。
            output['planning_status'] = 'model'
        calls.append(stage)
        getattr(coordinator, 'accept_'+stage)(child.child_key, activation=handle, now=113., output=output)
        getattr(coordinator, 'freeze_'+stage)(child.child_key, activation=handle, now=114.)
        getattr(coordinator, 'resume_'+stage)(child.child_key, activation=handle, now=115.)
    pending = coordinator.prepare_suggestion(child.child_key, activation=handle, now=116.)
    assert pending.stage == 'suggestion' and pending.status == 'provider_pending'
    saved = rt.get_session_timeline('char_a')
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    rt.set_control_mode('char_a', 'player_priority_assisted')
    monkeypatch.setattr(rt._l3, 'prepare_intent_plan', lambda **_: pytest.fail('must not prepare third request again'))
    assert coordinator.prepare_suggestion(child.child_key, activation=handle, now=117.) == pending
    assert rt.get_session_timeline('char_a') == saved
    output = rt._l3._gateway.complete_prepared_request(pending.request_json.encode())
    calls.append('suggestion')
    coordinator.accept_suggestion(child.child_key, activation=handle, now=118., output=output)
    planned = coordinator.freeze_suggestion(child.child_key, activation=handle, now=119.)
    assert rt.get_session_timeline('char_a') == saved
    assert [row['event_type'] for row in planned.plan['events']] == ['character_agent_suggestion_packet']
    completed = coordinator.resume_suggestion(child.child_key, activation=handle, now=120.)
    assert completed.status == 'completed' and calls == ['l2', 'l3', 'suggestion']
    assert rt.get_session_timeline('char_a')[-1]['payload'] == completed.frame['suggestion']
    assert completed.frame['commands'] == [] and admissions.list_pending() == ()
    writes = rt._session_store._connection.total_changes
    assert coordinator.resume_suggestion(child.child_key, activation=handle, now=121.) == completed
    assert rt._session_store._connection.total_changes == writes
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    assert rt._l3._consumed_behavior_policy_ids == ({'assisted-policy'} if with_policy else set())
    assert rt.get_session_timeline('char_a')[-1]['payload'] == completed.frame['suggestion']
    rt.close()

def test_auto_execution_plan_matches_original_without_writes(tmp_path):
    from app.models.character_agent_runtime import CharacterInterpretation
    from app.models.character_agent_runtime import CharacterIntentDecision
    from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    for stage in ('l2', 'l3'):
        pending = getattr(coordinator, 'prepare_'+stage)(child.child_key, activation=handle, now=112.)
        output = rt._l2._gateway.complete_prepared_request(pending.request_json.encode())
        getattr(coordinator, 'accept_'+stage)(child.child_key, activation=handle, now=113., output=output)
        getattr(coordinator, 'freeze_'+stage)(child.child_key, activation=handle, now=114.)
        ready = getattr(coordinator, 'resume_'+stage)(child.child_key, activation=handle, now=115.)
    before = rt._capture_cognition_pin('char_a')
    writes = rt._session_store._connection.total_changes
    planned = rt._plan_execution_effects(ready.frame)
    assert rt._capture_cognition_pin('char_a') == before
    assert rt._session_store._connection.total_changes == writes
    payload = ready.frame['normalized_payload']
    actual = rt._record_execution_plan('char_a', child.producer_ts,
        CharacterPrivateWorldSnapshot.model_validate(ready.frame['entry_after']['private_snapshot']),
        CharacterInterpretation.model_validate(ready.frame['interpretation']),
        CharacterIntentDecision.model_validate(ready.frame['decision']),
        causation_id=str(payload.get('causation_id', '') or ''),
        correlation_id=str(payload.get('correlation_id', '') or ''))
    assert planned['execution_plan'] == actual
    assert planned['continuity'] == rt.get_runtime_continuity_state('char_a')
    assert planned['commands'] == [item.model_dump(mode='json') for item in rt.filter_commands_for_actor(
        'char_a', rt._l4.build_commands_from_execution_plan(actual))]
    assert planned['events'] == [{key: rt.get_session_timeline('char_a')[-1][key]
        for key in ('event_type', 'producer_ts', 'payload')}]
    rt.close()

def test_execution_effects_resume_original_commands_after_reopen(tmp_path, monkeypatch):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    for stage in ('l2', 'l3'):
        pending = getattr(coordinator, 'prepare_'+stage)(child.child_key, activation=handle, now=112.)
        getattr(coordinator, 'accept_'+stage)(child.child_key, activation=handle, now=113.,
            output=rt._l2._gateway.complete_prepared_request(pending.request_json.encode()))
        getattr(coordinator, 'freeze_'+stage)(child.child_key, activation=handle, now=114.)
        getattr(coordinator, 'resume_'+stage)(child.child_key, activation=handle, now=115.)
    before = rt.get_session_timeline('char_a')
    planned = coordinator.freeze_execution(child.child_key, activation=handle, now=116.)
    assert rt.get_session_timeline('char_a') == before
    assert planned.plan['after']['commands']
    original_save = admissions.store.save_runtime_state
    def fail_continuity(*args, **kwargs):
        raise OSError('continuity transaction')
    monkeypatch.setattr(admissions.store, 'save_runtime_state', fail_continuity)
    with pytest.raises(OSError, match='continuity transaction'):
        coordinator.resume_execution(child.child_key, activation=handle, now=117.)
    assert rt.get_session_timeline('char_a') == before
    assert admissions.store.read_receipt('char_a', kind='cognition_stage', key=f'{child.child_key}/execution/effects') is None
    monkeypatch.setattr(admissions.store, 'save_runtime_state', original_save)
    original = admissions.advance_progress
    def crash(**kwargs):
        if kwargs['stage'] == 'execution' and kwargs['status'] == 'completed':
            raise OSError('after execution effect')
        return original(**kwargs)
    monkeypatch.setattr(admissions, 'advance_progress', crash)
    with pytest.raises(OSError, match='after execution effect'):
        coordinator.resume_execution(child.child_key, activation=handle, now=117.)
    saved = rt.get_session_timeline('char_a')
    continuity = rt.get_runtime_continuity_state('char_a')
    assert len(saved) == len(before)+1
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    assert rt.get_runtime_continuity_state('char_a') == continuity
    monkeypatch.setattr(rt, '_plan_execution_effects', lambda *_: pytest.fail('no new execution plan'))
    completed = coordinator.resume_execution(child.child_key, activation=handle, now=118.)
    assert completed.status == 'completed' and completed.frame == planned.plan['after']
    assert rt.get_session_timeline('char_a') == saved and admissions.list_pending() == ()
    assert rt.get_runtime_continuity_state('char_a') == continuity
    rt.close()

def test_background_wake_uses_private_snapshot_and_completes_original_agenda(tmp_path):
    rt, admissions, coordinator, seed, handle = setup(tmp_path)
    rt._l1.apply_siming_output(rt._plan_siming_entry(seed.payload)['normalized_payload'])
    rt.set_background_cognition_enabled(True)
    rt.set_background_mode('char_a', 'active')
    rt._refresh_weak_supervision_state(actor_id='char_a', producer_ts=9999, reason_summary='background enabled')
    child = admissions.admit(**{**request(), 'delivery_id': 'wake',
        'source_kind': 'run_background_cognition_tick', 'payload': {}, 'producer_ts': 10000})
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    entry_ready = coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    assert entry_ready.status == 'stage_ready', entry_ready.frame.get('background_result')
    for stage in ('l2', 'l3'):
        pending = getattr(coordinator, 'prepare_'+stage)(child.child_key, activation=handle, now=112.)
        getattr(coordinator, 'accept_'+stage)(child.child_key, activation=handle, now=113.,
            output=rt._l2._gateway.complete_prepared_request(pending.request_json.encode()))
        getattr(coordinator, 'freeze_'+stage)(child.child_key, activation=handle, now=114.)
        ready = getattr(coordinator, 'resume_'+stage)(child.child_key, activation=handle, now=115.)
    assert ready.status == 'completed' and ready.frame['commands'] == []
    assert ready.frame['background_result']['ran'] is True
    events = rt.get_session_timeline('char_a')
    assert events[-1]['event_type'] == 'character_background_cognition_event'
    assert not any(event['event_type'] in {'siming_output_event', 'character_agent_execution_request'} for event in events)
    agenda = rt.get_background_agenda_state('char_a')
    assert agenda and rt._last_background_tick_ms['char_a'] == 10000
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    assert rt.get_background_agenda_state('char_a') == agenda
    assert rt._last_background_tick_ms['char_a'] == 10000
    assert admissions.read_progress(child.child_key).status == 'completed'
    rt.close()

@pytest.mark.parametrize('blocked', ['disabled', 'off', 'missing_snapshot'])
def test_background_blocked_entry_is_terminal_without_model_or_perception(tmp_path, monkeypatch, blocked):
    rt, admissions, coordinator, seed, handle = setup(tmp_path)
    if blocked != 'missing_snapshot':
        rt._l1.apply_siming_output(rt._plan_siming_entry(seed.payload)['normalized_payload'])
    rt.set_background_cognition_enabled(blocked != 'disabled')
    rt.set_background_mode('char_a', 'off' if blocked == 'off' else 'active')
    rt._refresh_weak_supervision_state(actor_id='char_a', producer_ts=9999, reason_summary='configured gate')
    child = admissions.admit(**{**request(), 'delivery_id': 'blocked-wake', 'producer_ts': 10000})
    before = rt.get_session_timeline('char_a')
    monkeypatch.setattr(rt._l2, 'prepare_background_state', lambda *args, **kwargs: pytest.fail('blocked background cannot call model'))
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    result = coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    assert result.status == 'completed' and result.frame['background_result']['ran'] is False
    assert result.frame['background_result']['reason'] == {'disabled':'background_disabled', 'off':'actor_background_off', 'missing_snapshot':'missing_snapshot'}[blocked]
    assert rt.get_session_timeline('char_a') == before
    rt.close()

@pytest.mark.parametrize('second_source', ['background', 'siming'])
def test_second_background_pending_request_preserves_prior_tick_on_reopen(tmp_path, monkeypatch, second_source):
    rt, admissions, coordinator, seed, handle = setup(tmp_path)
    rt._l1.apply_siming_output(rt._plan_siming_entry(seed.payload)['normalized_payload'])
    rt.set_background_cognition_enabled(True)
    rt.set_background_mode('char_a', 'active')
    rt._refresh_weak_supervision_state(actor_id='char_a', producer_ts=9999, reason_summary='enabled')
    for tick in (10000, 20000):
        data = {**request(), 'delivery_id': f'wake:{tick}', 'producer_ts': tick}
        if tick == 20000 and second_source == 'siming':
            payload = dict(seed.payload, producer_ts=tick, delivery_id=f'wake:{tick}')
            data.update(source_kind='ingest_siming_output', payload=payload)
        child = admissions.admit(**data)
        coordinator.begin_entry(child.child_key, activation=handle, now=110.)
        coordinator.resume_entry(child.child_key, activation=handle, now=111.)
        pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
        if tick == 20000:
            break
        coordinator.accept_l2(child.child_key, activation=handle, now=113., output=rt._l2._gateway.complete_prepared_request(pending.request_json.encode()))
        coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
        coordinator.resume_l2(child.child_key, activation=handle, now=115.)
        pending = coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
        coordinator.accept_l3(child.child_key, activation=handle, now=117., output=rt._l3._gateway.complete_prepared_request(pending.request_json.encode()))
        coordinator.freeze_l3(child.child_key, activation=handle, now=118.)
        coordinator.resume_l3(child.child_key, activation=handle, now=119.)
    assert rt._last_background_tick_ms['char_a'] == 10000
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    rt.set_background_cognition_enabled(True)
    rt.set_background_mode('char_a', 'active')
    monkeypatch.setattr(rt._l2, 'prepare_background_state', lambda *args, **kwargs: pytest.fail('no reprepare'))
    assert rt._last_background_tick_ms['char_a'] == 10000
    assert coordinator.prepare_l2(child.child_key, activation=handle, now=120.) == pending
    rt.close()

@pytest.mark.parametrize('stage', ['l2', 'l3'])
def test_provider_error_is_frozen_and_reopens_into_original_continuity_floor(tmp_path, monkeypatch, stage):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    if stage == 'l3':
        coordinator.accept_l2(child.child_key, activation=handle, now=113., output={})
        coordinator.freeze_l2(child.child_key, activation=handle, now=114.)
        coordinator.resume_l2(child.child_key, activation=handle, now=115.)
        coordinator.prepare_l3(child.child_key, activation=handle, now=116.)
    pending = admissions.read_progress(child.child_key)
    before = rt.get_session_timeline('char_a')
    accepted = coordinator.accept_provider_error(child.child_key, activation=handle, now=117.,
        stage=stage, error=TimeoutError('provider deadline'))
    assert accepted.completion['error'] == {'type': 'TimeoutError', 'message': 'provider deadline'}
    assert accepted.request_json == pending.request_json
    assert rt.get_session_timeline('char_a') == before
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    monkeypatch.setattr(rt, '_continuity_floor_interpretation', lambda **_: pytest.fail('must not remake fallback'))
    monkeypatch.setattr(rt, '_continuity_floor_decision', lambda **_: pytest.fail('must not remake fallback'))
    planned = getattr(coordinator, f'freeze_{stage}')(child.child_key, activation=handle, now=118.)
    assert len(planned.plan['events']) == 1
    ready = getattr(coordinator, f'resume_{stage}')(child.child_key, activation=handle, now=119.)
    result = ready.frame['interpretation' if stage == 'l2' else 'decision']
    assert result['fallback_mode'] == 'continuity_floor'
    assert 'TimeoutError' in result['reasoning_trace_summary' if stage == 'l2' else 'rationale']
    assert rt.get_session_timeline('char_a')[:-1] == before
    rt.close()

def test_provider_error_preserves_require_online_and_strict_current_pin(tmp_path, monkeypatch):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    pending = coordinator.prepare_l2(child.child_key, activation=handle, now=112.)
    monkeypatch.setenv('CHARACTER_MODEL_REQUIRE_ONLINE', '1')
    with pytest.raises(TimeoutError, match='deadline'):
        coordinator.accept_provider_error(child.child_key, activation=handle, now=113., stage='l2', error=TimeoutError('deadline'))
    assert admissions.read_progress(child.child_key) == pending
    monkeypatch.delenv('CHARACTER_MODEL_REQUIRE_ONLINE')
    rt.set_background_mode('char_a', 'off')
    with pytest.raises(ValueError, match='stale_pin'):
        coordinator.accept_provider_error(child.child_key, activation=handle, now=114., stage='l2', error=TimeoutError('deadline'))
    assert admissions.read_progress(child.child_key) == pending
    rt.close()

def test_assisted_continuity_floor_commits_original_packet_without_third_provider(tmp_path, monkeypatch):
    rt, admissions, coordinator, child, handle = setup(tmp_path)
    rt.set_control_mode('char_a', 'player_priority_assisted')
    coordinator.begin_entry(child.child_key, activation=handle, now=110.)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.)
    for stage in ('l2', 'l3'):
        getattr(coordinator, 'prepare_'+stage)(child.child_key, activation=handle, now=112.)
        coordinator.accept_provider_error(child.child_key, activation=handle, now=113., stage=stage, error=TimeoutError('deadline'))
        getattr(coordinator, 'freeze_'+stage)(child.child_key, activation=handle, now=114.)
        ready = getattr(coordinator, 'resume_'+stage)(child.child_key, activation=handle, now=115.)
    monkeypatch.setattr(rt._l3, 'prepare_intent_plan', lambda **_: pytest.fail('floor must not call third model'))
    planned = coordinator.prepare_suggestion(child.child_key, activation=handle, now=116.)
    assert planned.status == 'commit_started' and planned.request_json is None
    before = rt.get_session_timeline('char_a')
    rt.close()
    rt, admissions, coordinator, _, handle = setup(tmp_path)
    rt.set_control_mode('char_a', 'player_priority_assisted')
    monkeypatch.setattr(rt, '_build_continuity_floor_suggestion', lambda **_: pytest.fail('must not rebuild original packet'))
    completed = coordinator.resume_suggestion(child.child_key, activation=handle, now=117.)
    assert completed.status == 'completed' and completed.frame['commands'] == []
    assert completed.frame['suggestion']['planning_status'] == 'continuity_floor'
    assert rt.get_session_timeline('char_a')[:-1] == before
    assert rt._l3._consumed_behavior_policy_ids == set()
    rt.close()
