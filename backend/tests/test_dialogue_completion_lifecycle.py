from concurrent.futures import ThreadPoolExecutor
from threading import Event, get_ident
from time import monotonic, time
import json

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.models.player_input import DialogueSubmit
from test_character_agent_activation_handoff import active_dialogue_decision, runtime
from test_cognition_completion_revision import perceived


def event(request_id='turn-1', actor='char_a'):
    return DialogueSubmit(player_id='p1', room_id='room_demo', actor_id='char_c',
        intent_type='dialogue_submit', producer_ts=90210, target_actor_id=actor,
        content='Hello', request_id=request_id)


def coordinator():
    main.reset_runtime_state()
    result = main._get_dialogue_coordinator()
    result.connect('connection:test')
    return result


def begin(owner, request_id='turn-1'):
    return owner.begin(event(request_id).model_dump_json().encode(),
        connection_ref='connection:test', deadline_monotonic=monotonic() + 60)


def complete(owner, advance):
    from app.services.dialogue_continuation import run_dialogue_provider
    completion = run_dialogue_provider(advance.job, advance.provider, Event(), lambda _: None)
    return owner.advance(advance.job, completion), completion


def response_count():
    return sum(row['event_type'] == 'character_agent_dialogue_response'
               for row in main.character_agent_runtime.get_session_timeline('char_a'))


def releases():
    return sum(row.event_type == 'population.activation.released'
               for row in main.gameplay_event_store.read_events())


def test_current_activation_cannot_be_bypassed_by_empty_cognition_token():
    instance = runtime()
    handle, _ = instance.begin_actor_activation('char_a', active_dialogue_decision(), producer_ts=1)
    before = instance.get_session_timeline('char_a')
    rejected = instance.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived())
    assert rejected.status == 'requeued' and rejected.reason == 'activation_invalid'
    assert instance.get_session_timeline('char_a') == before
    instance.finish_actor_activation(handle, reason='cancelled')


def test_sync_activation_callback_keeps_perceived_actor_distinct_from_target():
    instance = runtime()
    event = perceived().model_copy(update={'target_actor_id': 'char_b'})
    instance.activate_actor('char_a', active_dialogue_decision(), producer_ts=1,
        cognition_callback=lambda: instance.ingest_character_perceived_event(event))
    assert any(row['event_type'] == 'character_perceived_event'
               for row in instance.get_session_timeline('char_a'))


def test_reset_closes_existing_cognition_even_before_first_dialogue_ticket():
    main.reset_runtime_state()
    instance, store = main.character_agent_runtime, main.gameplay_event_store
    handle, _ = instance.begin_actor_activation('char_a', active_dialogue_decision(), producer_ts=1)
    advance = instance.prepare_cognition_job(source_kind='ingest_character_perceived_event', payload=perceived(),
        activation_lock_ref=handle.lock_ref, activation_token=handle.token,
        activation_is_current=instance.activation_is_current)
    main.reset_runtime_state()
    assert instance.pending_actor_activations() == ()
    assert instance.pending_cognition_jobs() == ()
    assert instance.commit_cognition_result(advance.next_job, output={}).status == 'zero_write'
    assert sum(row.event_type == 'population.activation.released' for row in store.read_events()) == 1


def test_cognition_cancel_hook_finishes_outer_lease_without_waiting_for_provider():
    owner = coordinator()
    advance = begin(owner)
    assert advance.job.stage == 'cognition'
    cognition_job = owner.runtime.pending_cognition_jobs()[0]
    owner.runtime.cancel_cognition_turn(cognition_job.turn_id, reason='external_cancel')
    assert not owner.runtime.pending_actor_activations()
    assert response_count() == 0 and releases() == 1


def test_dialogue_lease_covers_cognition_fallback_and_tts_until_final_writeback():
    owner = coordinator()
    advance = begin(owner)
    stages = []
    while advance.status == 'pending':
        assert main.activation_lock_is_active('char_a')
        assert response_count() == 0
        stages.append(advance.job.stage)
        advance, _ = complete(owner, advance)
    assert stages[-2:] == ['dialogue_generation', 'tts']
    assert advance.status == 'completed'
    assert response_count() == 1 and releases() == 1
    assert not main.activation_lock_is_active('char_a')


def test_required_online_cognition_failure_retries_exact_frozen_request(monkeypatch):
    owner = coordinator()
    advance = begin(owner)
    original = advance.job
    assert original.stage == 'cognition'
    monkeypatch.setenv('CHARACTER_MODEL_REQUIRE_ONLINE', '1')

    retry = owner.advance(original,
        json.dumps({'error': 'HTTPError: provider unavailable'}).encode())

    assert retry.status == 'pending' and retry.job.stage == 'cognition'
    assert retry.job.request_json == original.request_json and retry.job.token != original.token
    assert len(owner.runtime.pending_cognition_jobs()) == 1
    assert main.activation_lock_is_active('char_a') and releases() == 0
    monkeypatch.delenv('CHARACTER_MODEL_REQUIRE_ONLINE')
    while retry.status == 'pending':
        retry, _ = complete(owner, retry)
    assert retry.status == 'completed' and releases() == 1


def test_required_online_cognition_persistent_failure_is_bounded(monkeypatch):
    owner = coordinator()
    advance = begin(owner)
    original_request = advance.job.request_json
    tokens = []
    monkeypatch.setenv('CHARACTER_MODEL_REQUIRE_ONLINE', '1')

    for attempt in range(4):
        tokens.append(advance.job.token)
        advance = owner.advance(advance.job,
            json.dumps({'error': 'HTTPError: provider unavailable'}).encode())
        if attempt < 3:
            assert advance.status == 'pending'
            assert advance.job.request_json == original_request

    assert len(set(tokens)) == 4
    assert advance.status == 'failed'
    assert advance.reason == 'cognition_provider_retry_exhausted'
    assert owner.runtime.pending_cognition_jobs() == ()
    assert not main.activation_lock_is_active('char_a')
    assert response_count() == 0 and releases() == 1


@pytest.mark.parametrize('stage', ['dialogue_generation', 'tts'])
def test_cancelled_completion_is_zero_write_and_cannot_release_next_token(stage):
    owner = coordinator()
    advance = begin(owner)
    while advance.job.stage != stage:
        advance, _ = complete(owner, advance)
    from app.services.dialogue_continuation import run_dialogue_provider
    payload = run_dialogue_provider(advance.job, advance.provider, Event(), lambda _: None)
    owner.cancel(advance.job.ticket_id, reason='cancelled')
    newer = begin(owner, 'turn-2')
    assert owner.advance(advance.job, payload).status == 'zero_write'
    assert main.activation_lock_is_active('char_a')
    assert response_count() == 0 and releases() == 1
    owner.cancel(newer.job.ticket_id, reason='cancelled')


def test_completion_replay_is_idempotent_and_conflicting_payload_is_rejected():
    owner = coordinator()
    advance = begin(owner)
    while advance.job.stage != 'tts':
        advance, _ = complete(owner, advance)
    final_job = advance.job
    finished, payload = complete(owner, advance)
    assert finished.status == 'completed'
    assert owner.advance(final_job, payload).replayed
    conflicting = json.dumps({'output': {'mode': 'invalid'}}).encode()
    assert owner.advance(final_job, conflicting).status == 'zero_write'
    assert response_count() == 1 and releases() == 1


def test_real_websocket_provider_wait_leaves_owner_available_and_all_writes_on_owner(monkeypatch):
    main.reset_runtime_state()
    with TestClient(main.component_app) as client:
        instance = main.character_agent_runtime
        owner_thread = main.runtime_execution.submit(get_ident).result(2)
        mutations = []
        provider_threads = []
        for name in ('begin_actor_activation', 'prepare_cognition_job', 'commit_cognition_result',
                     'record_dialogue_response', 'finish_actor_activation'):
            original = getattr(instance, name)
            def traced(*args, _name=name, _original=original, **kwargs):
                mutations.append((_name, get_ident()))
                return _original(*args, **kwargs)
            monkeypatch.setattr(instance, name, traced)
        started, release = Event(), Event()
        gateway = main.character_service.dialogue._gateway
        original_stream = gateway.stream_prepared_request
        def stream(request_json, *, cancelled):
            provider_threads.append(get_ident())
            started.set()
            assert release.wait(5)
            yield from original_stream(request_json, cancelled=cancelled)
        monkeypatch.setattr(gateway, 'stream_prepared_request', stream)
        with client.websocket_connect('/ws') as websocket:
            websocket.send_json({'message_type': 'player_input', 'payload': event().model_dump()})
            assert websocket.receive_json()['message_type'] == 'ack'
            assert websocket.receive_json()['message_type'] == 'dialogue_stream_start'
            try:
                assert started.wait(5)
                assert main.runtime_execution.submit(lambda: instance.activation_is_current(
                    instance.pending_actor_activations()[0].lock_ref,
                    instance.pending_actor_activations()[0].token)).result(1)
                assert main.runtime_execution.submit(response_count).result(1) == 0
            finally:
                release.set()
            messages = [websocket.receive_json() for _ in range(3)]
            assert [row['message_type'] for row in messages] == ['dialogue_stream_delta', 'dialogue_response', 'dialogue_stream_end']
        assert mutations and {thread for _, thread in mutations} == {owner_thread}
        assert provider_threads and owner_thread not in provider_threads


def test_cancelled_running_providers_keep_all_four_slots_until_real_exit():
    from app.services.dialogue_continuation import DialogueProviderSlots, PreparedDialogueJob
    pool = DialogueProviderSlots()
    release = Event()
    started = [Event() for _ in range(4)]
    class Provider:
        def __init__(self, index):
            self.index = index
        def complete_prepared_request(self, _request):
            started[self.index].set()
            assert release.wait(5)
            return {}
    slots, futures = [], []
    try:
        for index in range(4):
            slot = pool.acquire()
            slots.append(slot)
            futures.append(slot.submit(PreparedDialogueJob(str(index), str(index), 'cognition', 'char_a', b'{}'),
                                       Provider(index), Event(), lambda _: None))
        assert all(signal.wait(2) for signal in started)
        for slot in slots:
            slot.close()
        assert pool.acquire() is None
    finally:
        release.set()
        for future in futures:
            future.result(2)
    replacement = pool.acquire()
    assert replacement is not None
    replacement.close()


@pytest.mark.parametrize('stage', ['cognition', 'dialogue_generation', 'tts'])
@pytest.mark.parametrize('ending', ['cancel', 'revoke', 'renew', 'disconnect', 'deadline', 'reset', 'shutdown'])
def test_late_provider_completion_after_lifecycle_end_never_writes(stage, ending, monkeypatch):
    from app.services.dialogue_continuation import run_dialogue_provider
    from app.services.websocket_session_auth_service import WebSocketSessionEnrollment
    import app.character_agent.runtime.runtime_loop as runtime_module
    main.reset_runtime_state()
    with TestClient(main.component_app):
        execution = main.runtime_execution
        owner = execution.submit(main._get_dialogue_coordinator).result(2)
        instance, store = owner.runtime, main.gameplay_event_store
        closed_timeline, append_calls = [], []
        original_close, original_append = instance.close, instance._session_store.append_event
        def close():
            if not closed_timeline:
                closed_timeline.append(instance.get_session_timeline('char_a'))
            original_close()
        def append(*args, **kwargs):
            append_calls.append((args, kwargs))
            return original_append(*args, **kwargs)
        def timeline():
            return closed_timeline[0] if closed_timeline else instance.get_session_timeline('char_a')
        monkeypatch.setattr(instance, 'close', close)
        monkeypatch.setattr(instance._session_store, 'append_event', append)
        def setup():
            owner.connect('connection:test')
            credential = owner.auth.create_trusted_local_launch_credential(principal_ref='player',
                allowed_actor_refs=('unrelated-mirror-scope',), issued_at=int(time()), expires_at=int(time()) + 60)
            binding = owner.auth.bind_session(WebSocketSessionEnrollment(credential_kind='trusted_local_launch',
                credential=credential, protocol_version=1), remote_host='127.0.0.1', now=int(time())).binding
            owner.bind('connection:test', binding)
            return binding, begin(owner)
        binding, advance = execution.submit(setup).result(2)
        while advance.job.stage != stage:
            payload = run_dialogue_provider(advance.job, advance.provider, Event(), lambda _: None)
            job = advance.job
            advance = execution.submit(lambda: owner.advance(job, payload)).result(2)
        job = advance.job
        started, release = Event(), Event()
        def blocked_provider():
            started.set()
            assert release.wait(5)
            # 故意不观察业务取消，模拟不可中断 HTTP 的晚到结果。
            return run_dialogue_provider(job, advance.provider, Event(), lambda _: None)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(blocked_provider)
            try:
                assert started.wait(2)
                if ending == 'cancel':
                    execution.submit(lambda: owner.cancel(job.ticket_id, reason='cancelled')).result(2)
                elif ending == 'revoke':
                    assert main.revoke_websocket_session_for_transport(session_ref=binding.session_ref,
                        connection_ref='connection:test', reason_code='revoked', now=int(time()))
                elif ending == 'renew':
                    def renew():
                        owner.auth.issue_replacement_enrollment(binding.session_ref, int(time()))
                        owner.bind('connection:test', None)
                    execution.submit(renew).result(2)
                elif ending == 'disconnect':
                    execution.submit(lambda: owner.disconnect('connection:test')).result(2)
                elif ending == 'deadline':
                    monkeypatch.setattr(runtime_module, 'monotonic', lambda: monotonic() + 100)
                    execution.submit(lambda: owner.cancel(job.ticket_id, reason='deadline_expired')).result(2)
                elif ending == 'reset':
                    execution.submit(main._reset_runtime_state).result(2)
                else:
                    execution.submit(main.close_runtime_resources).result(2)
                before = execution.submit(timeline).result(2)
                writes_before = len(append_calls)
                if ending == 'reset':
                    new_before = execution.submit(lambda: main.character_agent_runtime.get_session_timeline('char_a')).result(2)
            finally:
                release.set()
            payload = future.result(2)
        assert execution.submit(lambda: owner.advance(job, payload)).result(2).status == 'zero_write'
        assert execution.submit(timeline).result(2) == before
        assert len(append_calls) == writes_before
        assert not any(row['event_type'] == 'character_agent_dialogue_response' for row in before)
        assert sum(row.event_type == 'population.activation.released' for row in store.read_events()) == 1
        assert execution.submit(instance.pending_actor_activations).result(2) == ()
        if ending == 'reset':
            assert main.character_agent_runtime is not instance
            assert main.character_agent_runtime.get_session_timeline('char_a') == new_before


@pytest.mark.parametrize('stage', ['dialogue_generation', 'tts'])
@pytest.mark.parametrize('related', [True, False])
def test_fallback_and_tts_pin_reject_only_related_actor_changes(stage, related):
    owner = coordinator()
    advance = begin(owner)
    while advance.job.stage != stage:
        advance, _ = complete(owner, advance)
    from app.services.dialogue_continuation import run_dialogue_provider
    payload = run_dialogue_provider(advance.job, advance.provider, Event(), lambda _: None)
    owner.runtime.set_background_mode('char_a' if related else 'char_b', 'active')
    before = response_count()
    result = owner.advance(advance.job, payload)
    if related:
        assert result.status == 'zero_write' and response_count() == before and releases() == 1
    else:
        while result.status == 'pending':
            result, _ = complete(owner, result)
        assert result.status == 'completed' and response_count() == 1 and releases() == 1


def test_release_rejection_marks_owner_unhealthy_and_keeps_cleanup_obligation(monkeypatch):
    from app.population_continuity.models import ActivationReceipt
    main.reset_runtime_state()
    with TestClient(main.component_app):
        execution = main.runtime_execution
        owner = execution.submit(main._get_dialogue_coordinator).result(2)
        execution.submit(lambda: owner.connect('connection:test')).result(2)
        advance = execution.submit(lambda: begin(owner)).result(2)
        authority = owner.runtime._activation_authority
        original_release = authority.release_lock
        monkeypatch.setattr(authority, 'release_lock', lambda **_: ActivationReceipt(
            committed=False, status='rejected', profile_ref='character:char_a', stop_reason='release_failed'))
        with pytest.raises(RuntimeError, match='release_failed'):
            execution.submit(lambda: owner.cancel(advance.job.ticket_id, reason='cancelled')).result(2)
        assert execution.snapshot()['state'] == 'unhealthy'
        assert len(execution.submit(owner.runtime.pending_actor_activations).result(2)) == 1
        assert execution.submit(response_count).result(2) == 0
        monkeypatch.setattr(authority, 'release_lock', original_release)
        execution.submit(lambda: owner.close()).result(2)
        assert releases() == 1


@pytest.mark.parametrize('outcome', ['missing_completion', 'invalid_output', 'tts_failure'])
def test_provider_failures_finish_once_without_dialogue_write_or_generation_retry(outcome, monkeypatch):
    owner = coordinator()
    advance = begin(owner)
    while advance.job.stage != 'dialogue_generation':
        advance, _ = complete(owner, advance)
    provider_calls = []
    gateway = advance.provider
    original_stream = gateway.stream_prepared_request
    def stream(request, *, cancelled):
        provider_calls.append(request)
        if outcome == 'missing_completion':
            yield {'event': 'delta', 'delta': 'partial'}
        elif outcome == 'invalid_output':
            raise ValueError('invalid structured output')
        else:
            yield from original_stream(request, cancelled=cancelled)
    monkeypatch.setattr(gateway, 'stream_prepared_request', stream)
    if outcome == 'tts_failure':
        monkeypatch.setattr(main.character_service.tts, 'synthesize',
            lambda *_: (_ for _ in ()).throw(RuntimeError('tts failed')))
    while advance.status == 'pending':
        advance, _ = complete(owner, advance)
    assert advance.status == 'failed'
    assert len(provider_calls) == 1 and releases() == 1 and response_count() == 0


def test_busy_same_actor_does_not_ingest_or_materialize():
    owner = coordinator()
    first = begin(owner)
    before = main.gameplay_event_store.export_snapshot()
    timeline = owner.runtime.get_session_timeline('char_a')
    latest = main.character_perceived_input_service.get_latest('char_a')
    result = begin(owner, 'second')
    assert result.status == 'requeued'
    assert main.gameplay_event_store.export_snapshot() == before
    assert owner.runtime.get_session_timeline('char_a') == timeline
    assert main.character_perceived_input_service.get_latest('char_a') == latest
    owner.cancel(first.job.ticket_id, reason='cancelled')


def test_direct_speech_uses_same_tts_final_gate_and_never_calls_fallback(monkeypatch):
    from app.character_agent.runtime.cognition_continuation import CognitionAdvance
    from app.models.character_agent_runtime import CharacterGoalCommand
    owner = coordinator()
    command = CharacterGoalCommand(actor_id='char_a', command_type='speak', ttl_ms=1500,
        causation_id='test:speech', correlation_id='test:speech', producer_ts=90210, dialogue_text='direct speech')
    monkeypatch.setattr(owner, '_prepare_cognition', lambda *_: CognitionAdvance('completed', result=[command]))
    monkeypatch.setattr(owner.character_service, 'prepare_dialogue',
        lambda *_: (_ for _ in ()).throw(AssertionError('fallback must not run')))
    advance = begin(owner)
    assert advance.job.stage == 'tts' and main.activation_lock_is_active('char_a')
    finished, _ = complete(owner, advance)
    assert json.loads(finished.messages_json)[0]['payload']['content'] == 'direct speech'
    assert finished.status == 'completed' and response_count() == 1 and releases() == 1


def test_completed_commit_precedes_cancel_without_retracting_fact():
    owner = coordinator()
    advance = begin(owner)
    ticket = advance.job.ticket_id
    while advance.status == 'pending':
        advance, _ = complete(owner, advance)
    before = owner.runtime.get_session_timeline('char_a')
    assert owner.cancel(ticket, reason='cancelled').status == 'zero_write'
    assert owner.runtime.get_session_timeline('char_a') == before
    assert response_count() == 1 and releases() == 1


@pytest.mark.parametrize('drain_before_limit', [True, False])
def test_owner_queue_full_waits_without_stopping_healthy_owner_and_on_stop_cleanup(drain_before_limit):
    import asyncio
    from threading import Timer
    from app.services.runtime_execution import RuntimeExecution
    main.reset_runtime_state()
    owner = main._get_dialogue_coordinator()
    order = []
    def close():
        owner.close()
        order.append(('store_close', releases()))
    execution = RuntimeExecution(max_pending=1, on_stop=close)
    execution.submit(lambda: owner.connect('connection:test')).result(2)
    advance = execution.submit(lambda: begin(owner)).result(2)
    occupied, release = Event(), Event()
    execution.submit(lambda: (occupied.set(), release.wait(3)))
    assert occupied.wait(1)
    filler = execution.submit(lambda: None)
    timer = Timer(0.05 if drain_before_limit else 0.6, release.set)
    if timer:
        timer.start()
    try:
        command = lambda: owner.cancel(advance.job.ticket_id, reason='cancelled')
        assert asyncio.run(main._dialogue_owner_call(execution, command)).status == 'cancelled'
        assert releases() == 1 and response_count() == 0
        assert execution.snapshot()['state'] == 'running'
    finally:
        release.set()
        if timer:
            timer.join()
        assert execution.stop(timeout_seconds=2)
        execution.closed.result(2)
    assert order == [('store_close', 1)]
    assert response_count() == 0


@pytest.mark.parametrize('blocked_stage', ['l2_reasoning', 'l3_planning', 'tts'])
@pytest.mark.parametrize('assisted', [False, True])
def test_real_l2_l3_and_tts_waits_keep_mutations_on_owner(blocked_stage, assisted, monkeypatch):
    from app.services import dialogue_continuation
    from test_cognition_completion_revision import ModelGateway
    from app.character_agent.models.simulation_seed import CharacterContinuityCommand
    main.reset_runtime_state()
    with TestClient(main.component_app) as client:
        instance = main.character_agent_runtime
        execution = main.runtime_execution
        owner_thread = execution.submit(get_ident).result(2)
        gateway = ModelGateway()
        instance._l2._gateway = instance._l3._gateway = gateway
        if assisted:
            execution.submit(lambda: instance.set_control_mode('char_a', 'player_priority_assisted')).result(2)
        mutations, providers = [], []
        for target, name in [(instance._session_store, 'append_event'), (instance._memory_store, 'write_event'),
                (instance._l1, 'apply_character_perceived_event'), (instance._l2, 'map_reasoning_output'),
                (instance._l3, 'finish_intent_plan'), (instance._need_tension_store, 'merge_delta'),
                (instance._dynamic_state_store, 'merge_delta'), (instance._goal_state_store, 'write'),
                (instance, 'finish_actor_activation')]:
            original = getattr(target, name)
            def traced(*args, _name=name, _original=original, **kwargs):
                mutations.append((_name, get_ident()))
                return _original(*args, **kwargs)
            monkeypatch.setattr(target, name, traced)
        original_context = main.character_service.dialogue._context_provider
        def context(actor_id):
            mutations.append(('context', get_ident()))
            return original_context(actor_id)
        monkeypatch.setattr(main.character_service.dialogue, '_context_provider', context)
        started, release = Event(), Event()
        original_provider = dialogue_continuation.run_dialogue_provider
        def blocked(job, provider, cancelled, emit):
            stage = json.loads(job.request_json).get('task_kind', job.stage)
            providers.append((stage, get_ident()))
            if stage == blocked_stage:
                started.set()
                assert release.wait(5)
            return original_provider(job, provider, cancelled, emit)
        monkeypatch.setattr(dialogue_continuation, 'run_dialogue_provider', blocked)
        with client.websocket_connect('/ws') as websocket:
            websocket.send_json({'message_type': 'player_input', 'payload': event().model_dump()})
            assert websocket.receive_json()['message_type'] == 'ack'
            assert websocket.receive_json()['message_type'] == 'dialogue_stream_start'
            try:
                assert started.wait(3)
                def unrelated_command():
                    return instance.apply_character_continuity_command(CharacterContinuityCommand(
                        command_id='other:1', actor_ref='character:char_b', expected_character_revision=0,
                        source_revision_vector={'world:test': 1}, state_delta={'dynamic_state': {'stress_load': 0.4}},
                        policy_revision='policy:character-continuity:v1', idempotency_key='other:1'))
                assert execution.submit(unrelated_command).result(1).status == 'committed'
                assert execution.submit(lambda: instance.activation_lock_is_active('char_a')).result(1)
                assert client.get('/health').status_code == 200
            finally:
                release.set()
            messages = []
            while not messages or messages[-1]['message_type'] != 'dialogue_stream_end':
                messages.append(websocket.receive_json())
            assert messages[-1]['payload']['status'] == 'completed'
        assert len([stage for stage, _ in providers if stage == 'l2_reasoning']) == 1
        assert len([stage for stage, _ in providers if stage == 'l3_planning']) == (2 if assisted else 1)
        assert {thread for _, thread in mutations} == {owner_thread}
        assert all(thread != owner_thread for _, thread in providers)
        assert execution.submit(response_count).result(2) == 1
        assert releases() == 1


@pytest.mark.parametrize('ending', ['cancel', 'revoke', 'renew', 'disconnect', 'overflow', 'deadline'])
def test_live_websocket_ends_while_provider_ignores_cancel(ending, monkeypatch):
    real_monotonic = monotonic
    expired, started, release, emit_more = Event(), Event(), Event(), Event()
    loop_held, burst_finished = Event(), Event()
    monkeypatch.setattr(main, 'monotonic', lambda: real_monotonic() + (100 if expired.is_set() else 0))
    main.reset_runtime_state()
    with TestClient(main.component_app, client=('127.0.0.1', 47112)) as client:
        execution = main.runtime_execution
        gateway = main.character_service.dialogue._gateway
        def stream(_request, *, cancelled):
            started.set()
            yield {'event': 'delta', 'delta': 'partial'}
            assert emit_more.wait(5)
            if ending == 'overflow':
                for _ in range(200):
                    yield {'event': 'delta', 'delta': 'x'}
                burst_finished.set()
            elif ending == 'deadline':
                yield {'event': 'delta', 'delta': 'clock'}
            assert release.wait(5)
            yield {'event': 'completed', 'output': {'content': 'late response', 'tone': 'neutral'}}
        monkeypatch.setattr(gateway, 'stream_prepared_request', stream)
        try:
            with client.websocket_connect('/ws') as websocket:
                session_ref = ''
                if ending in {'revoke', 'renew'}:
                    now = int(time())
                    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
                        principal_ref='player', allowed_actor_refs=('other:mirror:scope',), issued_at=now, expires_at=now + 60)
                    websocket.send_json({'message_type': 'websocket_session_bind', 'payload': {
                        'credential_kind': 'trusted_local_launch', 'credential': credential, 'protocol_version': 1}})
                    assert websocket.receive_json()['payload']['accepted']
                    session_ref = websocket.receive_json()['payload']['session_ref']
                websocket.send_json({'message_type': 'player_input', 'payload': event().model_dump()})
                assert websocket.receive_json()['message_type'] == 'ack'
                assert websocket.receive_json()['message_type'] == 'dialogue_stream_start'
                assert websocket.receive_json()['message_type'] == 'dialogue_stream_delta'
                assert started.wait(1)
                if ending == 'cancel':
                    websocket.send_json({'message_type': 'dialogue_stream_cancel', 'payload': {'request_id': 'turn-1'}})
                    assert websocket.receive_json()['payload']['accepted']
                elif ending == 'revoke':
                    connection_ref = main.gameplay_mirror_connection_registry.connection_ref_for(session_ref=session_ref)
                    assert main.revoke_websocket_session_for_transport(session_ref=session_ref,
                        connection_ref=connection_ref, reason_code='revoked', now=int(time()))
                elif ending == 'renew':
                    websocket.send_json({'message_type': 'websocket_session_renewal', 'payload': {'protocol_version': 2}})
                elif ending == 'deadline':
                    expired.set()
                    emit_more.set()
                elif ending == 'overflow':
                    # 确定性模拟 loop 暂时无法排空；不依赖 CPU 调度速度制造溢出。
                    async def hold_loop_until_burst():
                        loop_held.set()
                        assert burst_finished.wait(2)
                    held = websocket.portal.start_task_soon(hold_loop_until_burst)
                    assert loop_held.wait(2)
                    emit_more.set()
                    held.result(2)
                if ending != 'disconnect':
                    messages = []
                    while not messages or messages[-1]['message_type'] != 'dialogue_stream_end':
                        messages.append(websocket.receive_json())
                    assert not any(row['message_type'] == 'dialogue_response' for row in messages)
                    assert messages[-1]['payload']['status'] == {'overflow': 'failed', 'deadline': 'timed_out'}.get(ending, 'cancelled')
                    assert execution.submit(response_count).result(1) == 0
                    assert execution.submit(releases).result(1) == 1
            assert execution.submit(response_count).result(1) == 0
        finally:
            emit_more.set()
            burst_finished.set()
            release.set()


def test_live_completion_normal_backpressure_waits_and_preserves_owner(monkeypatch):
    from app.services.runtime_execution import RuntimeQueueFull
    from time import monotonic
    started, release = Event(), Event()
    main.reset_runtime_state()
    with TestClient(main.component_app) as client:
        execution = main.runtime_execution
        original_submit = execution.submit
        response_writes = []
        original_record = main.character_agent_runtime.record_dialogue_response
        def record(**kwargs):
            response_writes.append(kwargs)
            return original_record(**kwargs)
        monkeypatch.setattr(main.character_agent_runtime, 'record_dialogue_response', record)
        gateway = main.character_service.dialogue._gateway
        def stream(_request, *, cancelled):
            started.set()
            assert release.wait(5)
            yield {'event': 'completed', 'output': {'content': 'never committed', 'tone': 'neutral'}}
        monkeypatch.setattr(gateway, 'stream_prepared_request', stream)
        with client.websocket_connect('/ws') as websocket:
            websocket.send_json({'message_type': 'player_input', 'payload': event().model_dump()})
            assert websocket.receive_json()['message_type'] == 'ack'
            assert websocket.receive_json()['message_type'] == 'dialogue_stream_start'
            assert started.wait(2)
            full_until=monotonic()+.6
            def temporarily_full(command):
                if monotonic()<full_until:raise RuntimeQueueFull('test_full')
                return original_submit(command)
            monkeypatch.setattr(execution, 'submit', temporarily_full)
            release.set()
            try:
                terminal = websocket.receive_json()
                while terminal['message_type'] != 'dialogue_stream_end':
                    terminal=websocket.receive_json()
                assert terminal['payload']['status'] == 'completed'
            finally:
                monkeypatch.setattr(execution, 'submit', original_submit)
        assert execution.snapshot()['state']=='running'
        assert releases() == 1 and len(response_writes) == 1


def test_agent_initiated_stream_start_preserves_speaking_actor():
    main.reset_runtime_state()
    with TestClient(main.component_app) as client:
        with client.websocket_connect('/ws') as websocket:
            request = event().model_copy(update={'player_id': 'character_agent', 'actor_id': 'char_b'})
            websocket.send_json({'message_type': 'player_input', 'payload': request.model_dump()})
            assert websocket.receive_json()['message_type'] == 'ack'
            start = websocket.receive_json()
            assert start['payload']['actor_id'] == 'char_b'
            assert start['payload']['target_actor_id'] == 'char_a'


def test_cancelled_queue_capacity_wait_does_not_stop_owner_and_real_stop_still_rejects():
    import asyncio
    from app.services.runtime_execution import RuntimeExecution, RuntimeStopped
    occupied, release = Event(), Event()
    execution = RuntimeExecution(max_pending=1)
    execution.submit(lambda: (occupied.set(), release.wait(3)))
    assert occupied.wait(1)
    execution.submit(lambda: None)
    async def cancel_wait():
        task=asyncio.create_task(main._dialogue_owner_call(execution, lambda: pytest.fail('cancelled command executed')))
        await asyncio.sleep(.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert execution.snapshot()['state']=='running'
    try:asyncio.run(cancel_wait())
    finally:
        release.set()
        assert execution.stop(timeout_seconds=2)
    with pytest.raises(RuntimeStopped):
        asyncio.run(main._dialogue_owner_call(execution, lambda: None))
