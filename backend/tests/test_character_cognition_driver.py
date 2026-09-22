import asyncio
import pytest
from threading import Event, get_ident
from urllib.error import HTTPError

from app.services.dialogue_continuation import DialogueProviderSlots
from app.services.runtime_execution import RuntimeExecution
from test_character_cognition_coordinator import setup
from test_character_agent_activation_handoff import active_dialogue_decision


def test_character_driver_uses_shared_slots_and_owner_keeps_progressing(tmp_path):
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver
    execution = RuntimeExecution()
    pool = DialogueProviderSlots()
    gate, entered = Event(), Event()
    threads = []
    def init():
        rt, admissions, coordinator, child, handle = setup(tmp_path)
        rt.finish_actor_activation(handle, reason='setup')
        return rt, admissions, coordinator, child, get_ident()
    rt, admissions, coordinator, child, owner = execution.submit(init).result(3)
    original = rt._l2._gateway.complete_prepared_request
    def provider(request):
        threads.append(get_ident())
        entered.set()
        assert gate.wait(5)
        return original(request)
    rt._l2._gateway.complete_prepared_request = provider
    async def owner_call(fn):
        return await asyncio.wrap_future(execution.submit(fn))
    async def check():
        completed = []
        driver = CharacterCognitionDriver(coordinator=coordinator, owner_call=owner_call, slots=pool,
            begin_activation=lambda entry: rt.begin_actor_activation(entry.actor_id, active_dialogue_decision(), producer_ts=entry.producer_ts)[0],
            on_completed=lambda entry, progress: completed.append(progress), clock=lambda: 120.)
        held = [pool.acquire() for _ in range(4)]
        await driver.poll()
        assert await owner_call(lambda: admissions.read_progress(child.child_key)) is None
        held.pop().close()
        await driver.poll()
        assert await asyncio.to_thread(entered.wait, 2)
        assert await owner_call(lambda: get_ident()) == owner
        assert pool.acquire() is None
        assert threads == [threads[0]] and owner not in threads
        gate.set()
        for _ in range(100):
            await driver.poll()
            if completed:
                break
            await asyncio.sleep(.01)
        assert completed and completed[0].status == 'completed'
        assert await owner_call(lambda: admissions.list_pending()) == ()
        assert await owner_call(rt.pending_actor_activations) == ()
        await driver.close()
        for slot in held:
            slot.close()
    try:
        asyncio.run(check())
    finally:
        gate.set()
        pool._executor.shutdown(wait=True)
        execution.submit(rt.close).result(3)
        execution.stop()


def test_character_driver_retries_exact_frozen_request_after_required_online_failure(tmp_path, monkeypatch):
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver
    execution, pool = RuntimeExecution(), DialogueProviderSlots()
    attempts = []
    def init():
        rt, admissions, coordinator, child, handle = setup(tmp_path)
        rt.finish_actor_activation(handle, reason='setup')
        return rt, admissions, coordinator, child
    rt, admissions, coordinator, child = execution.submit(init).result(3)
    def provider(request):
        attempts.append(request)
        if len(attempts) == 1:
            raise HTTPError('https://provider.invalid', 503, 'temporary transport failure', {}, None)
        restored = rt._l2._gateway._restore_prepared_request(request)
        return rt._l2._gateway._provider._offline_complete(restored)
    monkeypatch.setattr(rt._l2._gateway, 'complete_prepared_request', provider)
    monkeypatch.setattr(rt._l3._gateway, 'complete_prepared_request', provider)
    monkeypatch.setenv('CHARACTER_MODEL_REQUIRE_ONLINE', '1')
    async def owner_call(fn):
        return await asyncio.wrap_future(execution.submit(fn))
    async def check():
        completed = []
        driver = CharacterCognitionDriver(coordinator=coordinator, owner_call=owner_call, slots=pool,
            begin_activation=lambda entry: rt.begin_actor_activation(entry.actor_id, active_dialogue_decision(), producer_ts=entry.producer_ts)[0],
            on_completed=lambda entry, progress: completed.append(progress), clock=lambda: 120.)
        try:
            for _ in range(200):
                await driver.poll()
                if completed:
                    break
                await asyncio.sleep(.01)
            assert completed and completed[0].status == 'completed'
            assert len(attempts) == 3 and attempts[0] == attempts[1]
            assert execution.snapshot()['state'] == 'running'
            assert await owner_call(lambda: admissions.list_pending()) == ()
            assert await owner_call(rt.pending_actor_activations) == ()
        finally:
            await driver.close()
    try:
        asyncio.run(check())
    finally:
        pool._executor.shutdown(wait=True)
        execution.submit(rt.close).result(3)
        execution.stop()

@pytest.mark.parametrize('ending', ['cancel_prepare', 'submit', 'shutdown', 'close_prepare', 'source', 'source_begin'])
def test_character_driver_keeps_undelivered_lease_and_cancellation_holds_real_slot(tmp_path, monkeypatch, ending):
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver
    execution, pool = RuntimeExecution(), DialogueProviderSlots()
    release, entered = Event(), Event()
    def init():
        rt, admissions, c, child, handle = setup(tmp_path)
        rt.finish_actor_activation(handle, reason='setup')
        return rt, admissions, c, child
    rt, admissions, c, child = execution.submit(init).result(3)
    async def owner_call(fn):
        return await asyncio.wrap_future(execution.submit(fn))
    async def check():
        driver = CharacterCognitionDriver(coordinator=c, owner_call=owner_call, slots=pool,
            begin_activation=lambda entry: rt.begin_actor_activation(entry.actor_id, active_dialogue_decision(), producer_ts=entry.producer_ts)[0],
            on_completed=lambda *_: None, clock=lambda: 120.)
        if ending == 'source_begin':
            driver.begin_activation = lambda _: (_ for _ in ()).throw(ValueError('source_revoked'))
        if ending in {'source', 'source_begin'}:
            admissions._validate_source = lambda _: (_ for _ in ()).throw(ValueError('source_revoked'))
            await driver.poll()
            progress = await owner_call(lambda: admissions.read_progress(child.child_key))
            assert progress.status == 'stale' and progress.reason == 'source_revoked'
            assert not driver._handles and await owner_call(rt.pending_actor_activations) == ()
            await driver.close()
            return
        if ending == 'close_prepare':
            prepared, deliver = asyncio.Event(), asyncio.Event()
            async def held_call(fn):
                result = await owner_call(fn)
                if isinstance(result, tuple) and len(result) == 3 and result[0] == 'l2':
                    prepared.set()
                    await deliver.wait()
                return result
            driver.owner_call = held_call
            task = asyncio.create_task(driver.poll())
            await asyncio.wait_for(prepared.wait(), 2)
            await driver.close()
            deliver.set()
            await task
            assert not driver._active and not driver._handles
            slots = [pool.acquire() for _ in range(4)]
            assert all(slots)
            for slot in slots:
                slot.close()
            return
        if ending == 'cancel_prepare':
            original = c.prepare_l2
            def delayed(*args, **kwargs):
                result = original(*args, **kwargs)
                entered.set()
                assert release.wait(5)
                return result
            monkeypatch.setattr(c, 'prepare_l2', delayed)
            task = asyncio.create_task(driver.poll())
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert driver._active == {} and len(driver._handles) == 1
            monkeypatch.setattr(c, 'prepare_l2', original)
        elif ending == 'submit':
            original = pool._executor.submit
            monkeypatch.setattr(pool._executor, 'submit', lambda *_: (_ for _ in ()).throw(RuntimeError('submit failed')))
            with pytest.raises(RuntimeError, match='submit failed'):
                await driver.poll()
            assert len(driver._handles) == 1 and not driver._active
            monkeypatch.setattr(pool._executor, 'submit', original)
        original_provider = rt._l2._gateway.complete_prepared_request
        def blocked(request):
            entered.set()
            assert release.wait(5)
            return original_provider(request)
        entered.clear(); release.clear()
        monkeypatch.setattr(rt._l2._gateway, 'complete_prepared_request', blocked)
        await driver.poll()
        assert await asyncio.to_thread(entered.wait, 2)
        held = [pool.acquire() for _ in range(3)]
        assert all(held)
        await driver.close()
        assert pool.acquire() is None
        assert await owner_call(rt.pending_actor_activations) == ()
        pending = await owner_call(lambda: admissions.read_progress(child.child_key))
        assert pending.status == 'provider_pending'
        release.set()
        for slot in held:
            slot.close()
    try:
        asyncio.run(check())
    finally:
        release.set()
        pool._executor.shutdown(wait=True)
        execution.submit(rt.close).result(3)
        execution.stop()
