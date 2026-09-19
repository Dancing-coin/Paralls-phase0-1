from collections import Counter
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from threading import Event, get_ident
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import pytest

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.memory_recall import MissingRequiredMemoryEvidence
from app.character_agent.models.memory_consistency import MemoryFactClaim
from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.models.siming_character_bridge import SimingCharacterCompatibilityInput


class ModelGateway:
    def __init__(self):
        self.gateway = CharacterModelGateway()
        self.requests = []

    def prepare_run_request(self, **kwargs):
        kwargs['route_override'] = 'local_only'
        return self.gateway.prepare_run_request(**kwargs)

    def complete_prepared_request(self, request_json):
        self.requests.append(request_json)
        output = self.gateway.complete_prepared_request(request_json)
        if json.loads(request_json)['task_kind'] == 'l2_reasoning':
            output.update(cognition_status='model', fallback_mode=None,
                          dynamic_state_delta={'vigilance_level': 0.25})
        else:
            output.update(planning_status='model', fallback_mode=None)
        return output


def runtime():
    result = CharacterAgentRuntime()
    result._session_store._runtime_id = "equivalence"
    gateway = ModelGateway()
    result._l2 = CharacterAgentL2Service(gateway=gateway, profile_registry=result._profile_registry)
    result._l3 = CharacterAgentL3Service(gateway=gateway)
    return result


def perceived(actor='char_a', ts=300):
    return CharacterPerceivedEvent(actor_id=actor, percept_channel='visual', producer_ts=ts,
        room_id='room_demo', scene_id='scene_demo', zone_id='zone_focus',
        perceived_summary='visual_fact/fixed_gaze_on_target', source_candidate_event_id=f'visual:{actor}:{ts}',
        clarity_score=1.0, certainty_score=1.0)


def source_args(rt, source):
    if source == 'ingest_character_perceived_event':
        return {'payload': perceived()}
    if source == 'ingest_self_body_perceived_event':
        return {'payload': SelfBodyPerceivedEvent(actor_id='char_a', body_state_class='interaction_strain',
            producer_ts=300, room_id='room_demo', scene_id='scene_demo', zone_id='zone_focus',
            perceived_summary='body_state_result/interaction_strain=engaged', source_body_result_id='body:300')}
    if source == 'ingest_siming_output':
        return {'payload': SimingCharacterCompatibilityInput(message_id='siming:300', delivery_id='delivery:300',
            actor_id='char_a', input_type='siming_high_level_message', band='fact_reveal', producer_ts=300,
            room_id='room_demo', scene_id='scene_demo', zone_id='zone_focus', causation_id='siming:300',
            correlation_id='siming:300', presentation_hint='watch env_lamp', target_environment_id='env_lamp')}
    rt._l1.apply_character_perceived_event(perceived())
    rt.set_background_cognition_enabled(True)
    rt.set_background_mode('char_a', 'active')
    return {'actor_id': 'char_a', 'producer_ts': 10000}


def finish(rt, advance):
    jobs = []
    while advance.status == 'pending':
        job = advance.next_job
        jobs.append(job)
        gateway = rt._l2._gateway if job.task_kind == 'l2_reasoning' else rt._l3._gateway
        advance = rt.commit_cognition_result(job, output=gateway.complete_prepared_request(job.request_json))
    assert advance.status == 'completed'
    return advance.result, jobs


SOURCES = ['ingest_character_perceived_event', 'ingest_self_body_perceived_event',
           'ingest_siming_output', 'run_background_cognition_tick']


@pytest.mark.parametrize('source', SOURCES)
@pytest.mark.parametrize('assisted', [False, True])
def test_four_sources_share_sync_and_staged_business_body(source, assisted):
    sync, staged = runtime(), runtime()
    for rt in (sync, staged):
        if assisted:
            rt.set_control_mode('char_a', 'player_priority_assisted')
    sync_args, staged_args = source_args(sync, source), source_args(staged, source)
    expected = getattr(sync, source)(sync_args['payload']) if 'payload' in sync_args else getattr(sync, source)(**sync_args)
    advance = staged.prepare_cognition_job(source_kind=source, **staged_args)
    assert not staged._l2._gateway.requests
    actual, jobs = finish(staged, advance)
    assert actual == expected
    assert staged.get_session_timeline('char_a') == sync.get_session_timeline('char_a')
    assert staged.get_dynamic_state('char_a') == sync.get_dynamic_state('char_a')
    assert staged._need_tension_store.read('char_a') == sync._need_tension_store.read('char_a')
    assert staged.get_goal_state_history('char_a') == sync.get_goal_state_history('char_a')
    assert staged._pending_suggestions == sync._pending_suggestions
    assert len(jobs) == (3 if assisted and source != SOURCES[-1] else 2)
    assert len({job.read_set_digest for job in jobs}) == len(jobs)
    events = Counter(e['event_type'] for e in staged.get_session_timeline('char_a'))
    assert events['character_interpretation_event'] == 1
    assert events['goal_state_event'] == 1
    assert events['need_tension_state_event'] == (1 if source == SOURCES[0] else 0)
    assert events['character_agent_execution_request'] == (1 if not assisted and source != SOURCES[-1] else 0)
    assert events['character_agent_suggestion_packet'] == (1 if assisted and source != SOURCES[-1] else 0)
    if isinstance(actual, list) and not assisted:
        assert len(actual) == 1
    recorded = next(e['payload'] for e in staged.get_session_timeline('char_a') if e['event_type'] == 'l2_reasoning_request')
    assert recorded == json.loads(jobs[0].request_json)


def test_duplicate_conflict_and_token_are_zero_write():
    rt = runtime()
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived()).next_job
    with pytest.raises(FrozenInstanceError):
        job.actor_id = 'char_b'
    output = rt._l2._gateway.complete_prepared_request(job.request_json)
    assert rt.commit_cognition_result(replace(job, token='wrong'), output=output).status == 'zero_write'
    advance = rt.commit_cognition_result(job, output=output)
    before = deepcopy(rt.get_session_timeline('char_a'))
    replay = rt.commit_cognition_result(job, output=deepcopy(output))
    assert replay.next_job == advance.next_job
    assert replay.replayed is True
    assert rt.commit_cognition_result(job, output={**output, 'interpreted_summary': 'other'}).status == 'zero_write'
    assert rt.get_session_timeline('char_a') == before
    finish(rt, advance)


@pytest.mark.parametrize('stage', [1, 2, 3])
@pytest.mark.parametrize('mutation', ['l1', 'control', 'supervision', 'memory', 'dynamic', 'need', 'goal', 'profile', 'agenda'])
def test_related_change_rejects_completion_without_fallback(mutation, stage):
    rt = runtime()
    rt.set_control_mode('char_a', 'player_priority_assisted')
    advance = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived())
    for _ in range(stage - 1):
        job = advance.next_job
        advance = rt.commit_cognition_result(job, output=rt._l2._gateway.complete_prepared_request(job.request_json))
    job = advance.next_job
    if mutation == 'l1':
        rt._l1.apply_character_perceived_event(perceived(ts=900))
    elif mutation == 'control':
        rt.set_control_mode('char_a', 'agent_full_auto')
    elif mutation == 'supervision':
        rt._supervision_states['char_a'].last_reason_summary = 'changed'
    elif mutation == 'memory':
        rt._session_append_event(actor_id='char_a', event_type='test_memory', producer_ts=900, payload={})
    elif mutation == 'dynamic':
        rt._dynamic_state_store.merge_delta('char_a', {'vigilance_level': 0.75})
    elif mutation == 'need':
        rt._need_tension_store.merge_delta('char_a', {'safety_pressure': 0.75})
    elif mutation == 'goal':
        rt._goal_state_store.write('char_a', {'primary_goal': 'changed'})
    elif mutation == 'profile':
        rt._profile_registry.get('char_a').identity_core.canonical_name = 'changed'
    else:
        rt._last_background_tick_ms['char_a'] = 900
    before = deepcopy(rt.get_session_timeline('char_a'))
    rejected = rt.commit_cognition_result(job, output={})
    assert rejected.status == 'requeued' and rejected.reason == 'stale_context'
    assert rt.get_session_timeline('char_a') == before
    assert rt.commit_cognition_result(job, output={}).replayed
    assert not rt.pending_cognition_jobs()


def test_busy_cancel_deadline_reset_and_ended_hook_once():
    rt = runtime()
    ended = []
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(),
        on_finished=lambda turn, reason: ended.append((turn, reason))).next_job
    before = rt.get_session_timeline('char_a')
    assert rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(ts=900)).reason == 'actor_busy'
    assert rt.get_session_timeline('char_a') == before
    assert rt.cancel_cognition_turn(job.turn_id).status == 'requeued'
    rt.cancel_cognition_turn(job.turn_id)
    assert len(ended) == 1 and not rt.pending_cognition_jobs()
    assert rt.commit_cognition_result(job, output={}).status == 'zero_write'
    timed = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(ts=900),
        deadline_monotonic=monotonic() - 1)
    assert timed.reason == 'deadline_expired' and not rt.pending_cognition_jobs()
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(ts=1200)).next_job
    rt.reset_cognition_jobs()
    assert rt.commit_cognition_result(job, output={}).status == 'zero_write'
    assert not rt.pending_cognition_jobs()


def test_unrelated_actor_can_change_while_worker_is_blocked_and_mutations_stay_owner(monkeypatch):
    rt = runtime()
    owner = get_ident()
    mutations = []
    for obj, name in [(rt._session_store, 'append_event'), (rt._memory_store, 'write_event'),
                      (rt._goal_state_store, 'write'), (rt._dynamic_state_store, 'merge_delta'),
                      (rt._dynamic_state_store, 'write'), (rt._need_tension_store, 'write'),
                      (rt._need_tension_store, 'merge_delta'), (rt._l4, 'build_commands_from_execution_plan'),
                      (rt._l1, 'apply_character_perceived_event'), (rt._l2, 'map_reasoning_output'),
                      (rt._l3, 'finish_intent_plan'), (rt, '_refresh_weak_supervision_state')]:
        original = getattr(obj, name)
        def record(*args, _original=original, _name=name, **kwargs):
            mutations.append((_name, get_ident()))
            return _original(*args, **kwargs)
        setattr(obj, name, record)
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived()).next_job
    entered, release = Event(), Event()
    gateway = rt._l2._gateway
    request = job.request_json
    provider = gateway.gateway._provider.complete
    validator = gateway.gateway._validator.validate
    io_threads = []
    def blocked_provider(request):
        io_threads.append(('provider', get_ident()))
        entered.set()
        assert release.wait(5)
        return provider(request)
    def checked_validate(**kwargs):
        io_threads.append(('validate', get_ident()))
        return validator(**kwargs)
    monkeypatch.setattr(gateway.gateway._provider, 'complete', blocked_provider)
    monkeypatch.setattr(gateway.gateway._validator, 'validate', checked_validate)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(gateway.complete_prepared_request, request)
        assert entered.wait(5)
        rt.set_control_mode('char_b', 'player_priority_assisted')
        rt._l1.apply_character_perceived_event(perceived('char_b', 700))
        receipt = rt.apply_character_continuity_command(CharacterContinuityCommand(
            command_id='continuity:char_b:1', actor_ref='character:char_b', expected_character_revision=0,
            source_revision_vector={'world:test': 1}, state_delta={'dynamic_state': {'stress_load': 0.4}},
            policy_revision='policy:character-continuity:v1', idempotency_key='continuity:char_b:1'))
        assert receipt.status == 'committed'
        assert rt.get_dynamic_state('char_b')['stress_load'] == 0.4
        assert rt.get_continuity_revision('char_b') == 1
        assert rt.get_control_mode('char_b') == 'player_priority_assisted'
        release.set()
        advance = rt.commit_cognition_result(job, output=future.result(5))
        job = advance.next_job
        advance = rt.commit_cognition_result(job,
            output=pool.submit(gateway.complete_prepared_request, job.request_json).result(5))
    result, _ = finish(rt, advance)
    assert result
    assert {thread for _, thread in mutations} == {owner}
    assert Counter(name for name, _ in mutations)['build_commands_from_execution_plan'] == 1
    assert Counter(name for name, _ in io_threads) == {'provider': 2, 'validate': 2}
    assert all(thread != owner for _, thread in io_threads)


def test_receipts_are_bounded_and_evicted_completion_cannot_write():
    rt = runtime()
    first = None
    for index in range(18):
        advance = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(ts=300 + index * 1000))
        if first is None:
            first = advance.next_job
        finish(rt, advance)
    assert len(rt._cognition_receipts) == 32
    before = deepcopy(rt.get_session_timeline('char_a'))
    assert rt.commit_cognition_result(first, output={}).status == 'zero_write'
    assert rt.get_session_timeline('char_a') == before


def test_pending_capacity_rejects_before_perception_and_background_busy_keeps_due():
    rt = runtime()
    for actor in ['char_d', 'char_e']:
        rt._supported_actor_ids.add(actor)
        rt._profile_registry._profiles_by_actor_id[actor] = rt._profile_registry.get('char_a').model_copy(deep=True)
    for actor in ['char_a', 'char_b', 'char_c', 'char_d']:
        assert rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(actor)).status == 'pending'
    assert len(rt.pending_cognition_jobs()) == 4
    rejected = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived('char_e'))
    assert rejected.reason == 'pending_capacity'
    assert not rt.get_session_timeline('char_e')
    rt.reset_cognition_jobs()
    args = source_args(rt, SOURCES[-1])
    first = rt.prepare_cognition_job(source_kind=SOURCES[-1], **args)
    blocked = rt.run_background_cognition_tick(**args)
    assert blocked.ran is False and blocked.reason == 'actor_busy'
    assert 'char_a' not in rt._last_background_tick_ms
    rt.cancel_cognition_turn(first.next_job.turn_id)
    completed = rt.run_background_cognition_tick(**args)
    assert completed.ran and rt._last_background_tick_ms['char_a'] == args['producer_ts']


def test_activation_validation_and_worker_cannot_resume_owner():
    rt = runtime()
    with pytest.raises(ValueError, match='requires owner validation'):
        rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(),
            activation_lock_ref='activation:a', activation_token='token')
    assert not rt.get_session_timeline('char_a')
    valid = True
    ended = []
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(),
        activation_lock_ref='activation:a', activation_token='token',
        activation_is_current=lambda ref, token: valid and ref == 'activation:a' and token == 'token',
        on_finished=lambda *args: ended.append(args)).next_job
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match='owner thread'):
            pool.submit(rt.commit_cognition_result, job, output={}).result()
    valid = False
    before = deepcopy(rt.get_session_timeline('char_a'))
    assert rt.commit_cognition_result(job, output={}).reason == 'activation_invalid'
    assert rt.get_session_timeline('char_a') == before
    assert len(ended) == 1 and not rt.pending_cognition_jobs()


def test_pin_reads_are_pure_and_do_not_prepare_recall_or_build_memory(monkeypatch):
    rt = runtime()
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived()).next_job
    before = deepcopy((rt._session_store._events_by_actor, rt._supervision_states, rt._continuity_state,
                       rt._background_agenda_states, rt._l2._profile_cache))
    def forbidden(*args, **kwargs):
        pytest.fail('pin performed preparation or recall')
    for obj, name in [(rt, 'get_working_memory_state_record'), (rt, 'get_memory_record_bundle'),
                      (rt, '_supervision_state_for'), (rt, '_continuity_state_for'),
                      (rt._l2, 'prepare_perceived_event'), (rt._l3, 'prepare_intent_plan')]:
        monkeypatch.setattr(obj, name, forbidden)
    assert rt._capture_cognition_pin('char_a') == job.source_revision_vector
    assert rt._capture_cognition_pin('char_a') == job.source_revision_vector
    assert (rt._session_store._events_by_actor, rt._supervision_states, rt._continuity_state,
            rt._background_agenda_states, rt._l2._profile_cache) == before
    rt.cancel_cognition_turn(job.turn_id)


@pytest.mark.parametrize('stage', [1, 2, 3])
@pytest.mark.parametrize('termination', ['deadline', 'cancel', 'reset'])
def test_deadline_and_cancel_at_each_stage_do_not_fallback_or_write(monkeypatch, stage, termination):
    rt = runtime()
    rt.set_control_mode('char_a', 'player_priority_assisted')
    clock = monotonic()
    advance = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(), deadline_monotonic=clock + 10)
    for _ in range(stage - 1):
        job = advance.next_job
        advance = rt.commit_cognition_result(job, output=rt._l2._gateway.complete_prepared_request(job.request_json))
    job = advance.next_job
    before = deepcopy(rt.get_session_timeline('char_a'))
    if termination == 'deadline':
        monkeypatch.setattr('app.character_agent.runtime.runtime_loop.monotonic', lambda: clock + 11)
        assert rt.commit_cognition_result(job, output={}).reason == 'deadline_expired'
    elif termination == 'cancel':
        assert rt.cancel_cognition_turn(job.turn_id).reason == 'cancelled'
        assert rt.commit_cognition_result(job, output={}).status == 'zero_write'
    else:
        rt.reset_cognition_jobs()
        assert rt.commit_cognition_result(job, output={}).status == 'zero_write'
    assert rt.get_session_timeline('char_a') == before
    assert not rt._pending_suggestions and not rt.pending_cognition_jobs()


@pytest.mark.parametrize('online', [False, True])
def test_provider_failure_is_owner_fallback_or_online_error_with_once_cleanup(monkeypatch, online):
    rt = runtime()
    if online:
        monkeypatch.setenv('CHARACTER_MODEL_REQUIRE_ONLINE', '1')
    ended = []
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(),
        on_finished=lambda *args: ended.append(args)).next_job
    failure = ValueError('provider unavailable')
    if online:
        with pytest.raises(ValueError, match='provider unavailable'):
            rt.commit_cognition_result(job, error=failure)
        assert rt.commit_cognition_result(job, error=failure).replayed
    else:
        advance = rt.commit_cognition_result(job, error=failure)
        result, _ = finish(rt, advance)
        assert result
        assert any(e['payload'].get('cognition_status') == 'continuity_floor' for e in rt.get_session_timeline('char_a'))
    assert len(ended) == 1 and not rt.pending_cognition_jobs()


@pytest.mark.parametrize('deadline', [float('nan'), float('inf'), -float('inf')])
def test_deadline_must_be_finite_before_any_mutation(deadline):
    rt = runtime()
    with pytest.raises(ValueError, match='finite'):
        rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(), deadline_monotonic=deadline)
    assert not rt.get_session_timeline('char_a') and not rt.pending_cognition_jobs()


def test_reset_closes_all_turns_even_if_one_owner_release_hook_fails():
    rt = runtime()
    ended = []
    def fail_release(turn, reason):
        ended.append((turn, reason))
        raise RuntimeError('release failed')
    rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(), on_finished=fail_release)
    rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived('char_b'),
        on_finished=lambda *args: ended.append(args))
    with pytest.raises(RuntimeError, match='release failed'):
        rt.reset_cognition_jobs()
    assert not rt.pending_cognition_jobs() and len(ended) == 2


@pytest.mark.parametrize('missing_persists', [False, True])
def test_missing_memory_retries_prepare_once_and_never_replays_perception(monkeypatch, missing_persists):
    rt = runtime()
    event = perceived().model_copy(update={'target_object_id': 'obj_letter',
        'fact_claim': MemoryFactClaim(scope_ref='world:main', subject_ref='obj_letter', predicate='state',
            value='visible', valid_at=300, source_ref='visual:char_a:300')})
    prepare = rt._l2.prepare_perceived_event
    attempts = []
    focused_calls = []
    focused = rt.get_target_memory_record_bundle
    def recall(actor, subjects):
        focused_calls.append(get_ident())
        return focused(actor, subjects)
    def prepare_once(snapshot, event, **kwargs):
        attempts.append(get_ident())
        if len(attempts) == 1 or missing_persists:
            record = rt.get_memory_record_bundle('char_a').knowledge_memories[0]
            raise MissingRequiredMemoryEvidence(['knowledge:' + record.memory_id])
        return prepare(snapshot, event, **kwargs)
    monkeypatch.setattr(rt, 'get_target_memory_record_bundle', recall)
    monkeypatch.setattr(rt._l2, 'prepare_perceived_event', prepare_once)
    result, jobs = finish(rt, rt.prepare_cognition_job(source_kind=SOURCES[0], payload=event))
    assert result and len(attempts) == 2 and len(focused_calls) == 1
    assert set(attempts + focused_calls) == {get_ident()}
    assert len(jobs) == (1 if missing_persists else 2)
    counts = Counter(e['event_type'] for e in rt.get_session_timeline('char_a'))
    assert counts['character_perceived_event'] == counts['need_tension_state_event'] == 1


def test_provider_missing_memory_error_does_not_retry_prepare(monkeypatch):
    rt = runtime()
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived()).next_job
    monkeypatch.setattr(rt, 'get_target_memory_record_bundle', lambda *args: pytest.fail('provider error retried prepare'))
    advance = rt.commit_cognition_result(job, error=MissingRequiredMemoryEvidence(['knowledge:absent']))
    finish(rt, advance)
    counts = Counter(e['event_type'] for e in rt.get_session_timeline('char_a'))
    assert counts['character_perceived_event'] == counts['need_tension_state_event'] == counts['l2_reasoning_request'] == 1


@pytest.mark.parametrize('source', SOURCES)
def test_sync_rejected_completion_preserves_original_return_type(monkeypatch, source):
    rt = runtime()
    args = source_args(rt, source)
    clock = [100.0]
    monkeypatch.setattr('app.character_agent.runtime.runtime_loop.monotonic', lambda: clock[0])
    provider = rt._l2._gateway.complete_prepared_request
    def slow_provider(request):
        output = provider(request)
        clock[0] += 61
        return output
    monkeypatch.setattr(rt._l2._gateway, 'complete_prepared_request', slow_provider)
    result = getattr(rt, source)(args['payload']) if 'payload' in args else getattr(rt, source)(**args)
    if source == SOURCES[-1]:
        assert result.ran is False and result.reason == 'deadline_expired'
    else:
        assert result == []
    assert not rt.pending_cognition_jobs()


def test_every_stage_duplicate_replays_receipt_without_goal_policy_or_l4_write(monkeypatch):
    rt = runtime()
    rt.set_control_mode('char_a', 'player_priority_assisted')
    finished = []
    original = rt._l3.finish_intent_plan
    def finish_once(prepared, output):
        finished.append(prepared.request_json)
        return original(prepared, output)
    monkeypatch.setattr(rt._l3, 'finish_intent_plan', finish_once)
    advance = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived())
    while advance.status == 'pending':
        job = advance.next_job
        output = rt._l2._gateway.complete_prepared_request(job.request_json)
        advance = rt.commit_cognition_result(job, output=output)
        before = deepcopy((rt.get_session_timeline('char_a'), rt.get_goal_state_history('char_a'),
                           rt._pending_suggestions, rt._l3._consumed_behavior_policy_ids))
        replay = rt.commit_cognition_result(job, output=deepcopy(output))
        assert replay.replayed and replay.next_job == advance.next_job and replay.result == advance.result
        assert rt.commit_cognition_result(job, output={**output, 'extra': 'conflict'}).status == 'zero_write'
        assert (rt.get_session_timeline('char_a'), rt.get_goal_state_history('char_a'),
                rt._pending_suggestions, rt._l3._consumed_behavior_policy_ids) == before
    assert len(finished) == 2
    counts = Counter(e['event_type'] for e in rt.get_session_timeline('char_a'))
    assert counts['goal_state_event'] == counts['character_agent_suggestion_packet'] == 1
    assert counts['character_agent_execution_request'] == 0


def test_reasoning_log_storage_failure_is_not_model_fallback(monkeypatch):
    rt = runtime()
    original = rt._session_store.append_event
    def fail_log(*args, **kwargs):
        if kwargs.get('event_type') == 'l2_reasoning_request':
            raise OSError('storage unavailable')
        return original(*args, **kwargs)
    monkeypatch.setattr(rt._session_store, 'append_event', fail_log)
    with pytest.raises(OSError, match='storage unavailable'):
        rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived())
    assert not rt.pending_cognition_jobs()
    counts = Counter(e['event_type'] for e in rt.get_session_timeline('char_a'))
    assert counts['character_interpretation_event'] == counts['goal_state_event'] == 0


def test_sync_and_staged_mixed_calls_keep_busy_and_fail_closed():
    rt = runtime()
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived()).next_job
    before = deepcopy(rt.get_session_timeline('char_a'))
    assert rt.ingest_character_perceived_event(perceived(ts=900)) == []
    with ThreadPoolExecutor(max_workers=1) as pool:
        with pytest.raises(RuntimeError, match='owner thread'):
            pool.submit(rt.ingest_character_perceived_event, perceived('char_b')).result()
    assert rt.get_session_timeline('char_a') == before
    assert not rt.get_session_timeline('char_b')
    rt.cancel_cognition_turn(job.turn_id)


@pytest.mark.parametrize('failure_source', ['activation', 'pin'])
@pytest.mark.parametrize('release_fails', [False, True])
def test_completion_validation_error_closes_turn_and_allows_new_admission(monkeypatch, failure_source, release_fails):
    rt = runtime()
    ended = []
    fail = False
    failure = OSError(f'{failure_source} store unavailable')
    release_failure = RuntimeError('release failed')
    def finished(*args):
        ended.append(args)
        if release_fails:
            raise release_failure
    original_pin = rt._capture_cognition_pin
    def activation_is_current(ref, token):
        if fail and failure_source == 'activation':
            raise failure
        return True
    def read_pin(*args, **kwargs):
        if fail and failure_source == 'pin':
            raise failure
        return original_pin(*args, **kwargs)
    monkeypatch.setattr(rt, '_capture_cognition_pin', read_pin)
    job = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(),
        activation_lock_ref='activation:a', activation_token='token',
        activation_is_current=activation_is_current,
        on_finished=finished).next_job
    steps = rt._pending_cognition['char_a'].steps
    before = deepcopy(rt.get_session_timeline('char_a'))
    fail = True
    with pytest.raises(OSError) as raised:
        rt.commit_cognition_result(job, output={})
    assert raised.value is failure
    if release_fails:
        assert raised.value.__cause__ is release_failure
    assert not rt.pending_cognition_jobs() and steps.gi_frame is None
    assert ended == [(job.turn_id, 'failed')]
    assert rt.get_session_timeline('char_a') == before
    assert rt.commit_cognition_result(job, output={}).status == 'zero_write'
    assert ended == [(job.turn_id, 'failed')]
    fail = False
    new = rt.prepare_cognition_job(source_kind=SOURCES[0], payload=perceived(ts=900))
    assert new.status == 'pending'
    rt.cancel_cognition_turn(new.next_job.turn_id)
