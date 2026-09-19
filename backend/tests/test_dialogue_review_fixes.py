import asyncio
from threading import Event
from time import monotonic
import json

import pytest

import app.main as main
from app.character_agent.runtime.cognition_continuation import CognitionAdvance
from app.models.character_agent_runtime import CharacterGoalCommand
from app.services.dialogue_continuation import DialogueProviderSlots, run_dialogue_provider
from app.services.runtime_execution import RuntimeExecution
from test_dialogue_completion_lifecycle import coordinator, complete, event, releases


def agent_event():
    return event().model_copy(update={'player_id': 'character_agent', 'actor_id': 'char_b'})


def begin_agent(owner):
    return owner.begin(agent_event().model_dump_json().encode(), connection_ref='connection:test',
                       deadline_monotonic=monotonic() + 60)


@pytest.mark.parametrize('direct', [True, False])
def test_agent_response_keeps_actual_speaker_in_tts_response_and_session(direct, monkeypatch):
    owner = coordinator()
    commands = []
    if direct:
        commands = [CharacterGoalCommand(actor_id='char_a', command_type='speak', ttl_ms=1500,
            causation_id='test:speech', correlation_id='test:speech', producer_ts=90210,
            dialogue_text='reply from char_a')]
    monkeypatch.setattr(owner, '_prepare_cognition', lambda *_: CognitionAdvance('completed', result=commands))
    expected_speaker, expected_target = ('char_a', 'char_b') if direct else ('char_b', 'char_a')
    tts_actors = []
    original_tts = owner.character_service.tts.synthesize
    def synthesize(actor_id, content):
        tts_actors.append(actor_id)
        return original_tts(actor_id, content)
    monkeypatch.setattr(owner.character_service.tts, 'synthesize', synthesize)
    advance = begin_agent(owner)
    while advance.status == 'pending':
        advance, _ = complete(owner, advance)
    response = json.loads(advance.messages_json)[0]['payload']
    assert (response['actor_id'], response['target_actor_id']) == (expected_speaker, expected_target)
    assert tts_actors == [expected_speaker]
    recorded = [actor for actor in ('char_a', 'char_b') if any(
        row['event_type'] == 'character_agent_dialogue_response'
        for row in owner.runtime.get_session_timeline(actor))]
    assert recorded == [expected_speaker]
    assert releases() == 1


@pytest.mark.parametrize('stage', ['dialogue_generation', 'tts'])
@pytest.mark.parametrize('changed_actor', ['char_a', 'char_b', 'char_c'])
def test_agent_fallback_pins_both_participants_but_not_unrelated_actor(stage, changed_actor):
    owner = coordinator()
    advance = begin_agent(owner)
    while advance.job.stage != stage:
        advance, _ = complete(owner, advance)
    payload = run_dialogue_provider(advance.job, advance.provider, Event(), lambda _: None)
    owner.runtime.set_background_mode(changed_actor, 'active')
    result = owner.advance(advance.job, payload)
    if changed_actor != 'char_c':
        assert result.status == 'zero_write' and result.reason == 'context_stale'
    else:
        while result.status == 'pending':
            result, _ = complete(owner, result)
        assert result.status == 'completed'
    recorded = [row for row in owner.runtime.get_session_timeline('char_b')
                if row['event_type'] == 'character_agent_dialogue_response']
    assert len(recorded) == (1 if changed_actor == 'char_c' else 0)
    assert releases() == 1


@pytest.mark.parametrize('blocked_message', ['ack', 'dialogue_stream_start', 'dialogue_stream_delta'])
def test_admission_deadline_cleans_up_while_transport_and_terminal_send_are_blocked(blocked_message, monkeypatch):
    async def scenario():
        main.reset_runtime_state()
        execution = RuntimeExecution(on_stop=main.close_runtime_resources)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        pool = DialogueProviderSlots()
        monkeypatch.setattr(main, '_dialogue_provider_slots', pool)
        owner = execution.submit(main._get_dialogue_coordinator).result(2)
        monkeypatch.setattr(owner, '_prepare_cognition', lambda *_: CognitionAdvance('completed', result=[]))
        blocked, released = asyncio.Event(), asyncio.Event()
        provider_exit = Event()
        loop = asyncio.get_running_loop()
        original_finish = owner.runtime.finish_actor_activation
        def finish(*args, **kwargs):
            receipt = original_finish(*args, **kwargs)
            loop.call_soon_threadsafe(released.set)
            return receipt
        monkeypatch.setattr(owner.runtime, 'finish_actor_activation', finish)
        clock_calls = 0
        def short_admission_deadline():
            nonlocal clock_calls
            clock_calls += 1
            return monotonic() - 59.75 if clock_calls == 1 else monotonic()
        monkeypatch.setattr(main, 'monotonic', short_admission_deadline)
        def stream(_request, *, cancelled):
            yield {'event': 'delta', 'delta': 'partial'}
            assert provider_exit.wait(4)
            yield {'event': 'completed', 'output': {'content': 'late', 'tone': 'neutral'}}
        monkeypatch.setattr(owner.character_service.dialogue._gateway, 'stream_prepared_request', stream)

        class WebSocket:
            query_params = {}
            client = None
            sent = False
            async def accept(self):
                pass
            async def send_json(self, message):
                if message['message_type'] in {blocked_message, 'dialogue_stream_end'}:
                    if message['message_type'] == blocked_message:
                        blocked.set()
                    await asyncio.Event().wait()
            async def receive_json(self):
                if not self.sent:
                    self.sent = True
                    return {'message_type': 'player_input', 'payload': event().model_dump()}
                await asyncio.Event().wait()

        task = asyncio.create_task(main.websocket_endpoint(WebSocket()))
        try:
            await asyncio.wait_for(blocked.wait(), 2)
            await asyncio.wait_for(released.wait(), 1.5)
            assert await asyncio.wrap_future(execution.submit(owner.runtime.pending_actor_activations)) == ()
            assert await asyncio.wrap_future(execution.submit(releases)) == 1
            # terminal send 仍被阻塞；只有真正运行中的 provider 可以继续占槽。
            slots = [pool.acquire() for _ in range(4)]
            assert sum(slot is not None for slot in slots) == (3 if blocked_message == 'dialogue_stream_delta' else 4)
            for slot in slots:
                if slot:
                    slot.close()
        finally:
            provider_exit.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.to_thread(execution.stop, timeout_seconds=2)
            execution.closed.result(2)
            pool._executor.shutdown(wait=True)
    asyncio.run(scenario())
