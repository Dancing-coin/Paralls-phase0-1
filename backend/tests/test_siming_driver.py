from threading import Event, get_ident
import pytest

from app.services.dialogue_continuation import DialogueProviderSlots


def test_siming_runner_uses_existing_four_slots_and_cancellation_waits_for_io():
    pool = DialogueProviderSlots()
    release = Event()
    started = [Event() for _ in range(4)]
    caller = get_ident()
    threads = []

    def runner(job, provider, cancelled, emit):
        threads.append(get_ident())
        started[job].set()
        assert release.wait(5)
        return provider

    slots, futures = [], []
    try:
        for index in range(4):
            slot = pool.acquire()
            slots.append(slot)
            futures.append(slot.submit(index, b'completion', Event(), lambda _: None, runner=runner))
        assert all(signal.wait(2) for signal in started)
        assert caller not in threads
        for slot in slots:
            slot.close()
        assert pool.acquire() is None
    finally:
        release.set()
        for slot in slots:
            slot.close()
        for future in futures:
            assert future.result(2) == b'completion'
        pool._executor.shutdown(wait=True)
    replacement = pool.acquire()
    assert replacement is not None
    replacement.close()


def test_driver_backs_off_and_bounds_generic_provider_retries(tmp_path):
    import asyncio
    import time
    from app.services.runtime_execution import RuntimeExecution
    from app.services.siming_driver import SimingDriver
    from app.services.siming_coordinator import SimingCoordinator
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_admission import SimingAdmissionService
    from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
    from app.services.siming_llm_provider import SimingLlmProviderError
    from test_siming_continuation import make_visual_fact_event

    attempts, retry_now = [], [0.]
    class Provider:
        def generate_candidates(self, **_kwargs):
            attempts.append(get_ident())
            raise SimingLlmProviderError('provider unavailable')

    execution, pool = RuntimeExecution(), DialogueProviderSlots()
    def setup_owner():
        graph = InMemoryHeavenlyGraphAdapter()
        runtime = SimingRuntime(llm_provider=Provider(), actor_pin_reader=lambda _: 1,
                                source_pin_reader=lambda _: True)
        owner = SimingCoordinator(runtime=runtime, graph=graph,
            admissions=SimingAdmissionService(SimingHeavenlyMemoryService(graph)),
            invalidation_reader=lambda _: None)
        event = make_visual_fact_event()
        key = owner.admit_event(event, now=time.time(), expires_at=time.time() + 60,
                                policy_version='v1').entry.key
        return owner, key
    owner, key = execution.submit(setup_owner).result(2)
    async def owner_call(command):
        return await asyncio.wrap_future(execution.submit(command))
    async def check():
        driver = SimingDriver(coordinator=owner, owner_call=owner_call, slots=pool,
                              clock=time.time, retry_clock=lambda: retry_now[0])
        try:
            for expected_attempts, delay in ((1, 1), (2, 2), (3, 4), (4, 0)):
                for _ in range(100):
                    await driver.poll()
                    if len(attempts) == expected_attempts and not driver._active:
                        break
                    await asyncio.sleep(.005)
                assert len(attempts) == expected_attempts
                if delay:
                    await driver.poll()
                    assert len(attempts) == expected_attempts
                    retry_now[0] += delay
            entry = await owner_call(lambda: owner.admissions.read(key).entry)
            assert entry.state == 'failed'
            assert entry.transition.reason == 'provider_failed:SimingLlmProviderError'
            assert await owner_call(lambda: owner.runtime.pending_count) == 0
        finally:
            await driver.close()
    try:
        asyncio.run(check())
    finally:
        pool._executor.shutdown(wait=True)
        execution.stop()


@pytest.mark.parametrize('ending', ['shutdown', 'complete', 'failure', 'submit', 'owner', 'cancel_prepare', 'read_prepare', 'cancel_cleanup', 'submit_cleanup'])
def test_driver_prepares_on_owner_after_slot_and_worker_never_owns_runtime(ending, monkeypatch):
    import asyncio
    import time
    from app.services.runtime_execution import RuntimeExecution
    from app.services.siming_driver import SimingDriver
    from app.services.siming_coordinator import SimingCoordinator
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_admission import SimingAdmissionService
    from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
    from test_siming_continuation import make_visual_fact_event

    release = Event()
    calls = []
    class Provider:
        def generate_candidates(self, **kwargs):
            calls.append(get_ident())
            assert release.wait(5)
            if ending == 'failure' and kwargs['recent_events'][0].room_id == 'room:0':
                raise OSError('provider connection lost')
            return []

    execution = RuntimeExecution(max_pending=1)
    pool = DialogueProviderSlots()
    def setup():
        graph = InMemoryHeavenlyGraphAdapter()
        runtime = SimingRuntime(llm_provider=Provider(), actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
        owner = SimingCoordinator(runtime=runtime, graph=graph,
            admissions=SimingAdmissionService(SimingHeavenlyMemoryService(graph)), invalidation_reader=lambda _: None)
        keys = []
        for index in range(5):
            event = make_visual_fact_event().model_copy(update={'room_id': f'room:{index}'})
            keys.append(owner.admit_event(event, now=time.time(), expires_at=time.time() + 60, policy_version='v1').entry.key)
        return owner, keys, get_ident()
    owner, keys, owner_thread = execution.submit(setup).result(2)
    async def owner_call(command):
        return await asyncio.wrap_future(execution.submit(command))
    async def check():
        driver = SimingDriver(coordinator=owner, owner_call=owner_call, slots=pool)
        try:
            if ending in {'cancel_prepare', 'read_prepare', 'cancel_cleanup', 'submit_cleanup'}:
                original_prepare = owner.prepare_ready
                prepared_signal, finish_prepare = Event(), Event()
                def interrupted_prepare(*args, **kwargs):
                    value = original_prepare(*args, **kwargs)
                    prepared_signal.set()
                    assert finish_prepare.wait(5)
                    return value
                async def congested_cleanup(command):
                    entered, unblock = Event(), Event()
                    def occupy():
                        entered.set()
                        assert unblock.wait(5)
                    busy = execution.submit(occupy)
                    assert await asyncio.to_thread(entered.wait, 2)
                    tail = execution.submit(lambda: None)
                    try:
                        return await owner_call(command)
                    finally:
                        unblock.set()
                        await asyncio.gather(asyncio.wrap_future(busy), asyncio.wrap_future(tail))
                if ending == 'submit_cleanup':
                    original_submit = pool._executor.submit
                    def fail_submit(*args, **kwargs):
                        monkeypatch.setattr(pool._executor, 'submit', original_submit)
                        driver.owner_call = congested_cleanup
                        raise RuntimeError('executor submit failed')
                    monkeypatch.setattr(pool._executor, 'submit', fail_submit)
                    from app.services.runtime_execution import RuntimeQueueFull
                    with pytest.raises(RuntimeQueueFull):
                        await driver.poll()
                    driver.owner_call = owner_call
                elif ending in {'cancel_prepare', 'cancel_cleanup'}:
                    monkeypatch.setattr(owner, 'prepare_ready', interrupted_prepare)
                    poll = asyncio.create_task(driver.poll())
                    assert await asyncio.to_thread(prepared_signal.wait, 2)
                    if ending == 'cancel_cleanup':
                        driver.owner_call = congested_cleanup
                    poll.cancel()
                    finish_prepare.set()
                    from app.services.runtime_execution import RuntimeQueueFull
                    with pytest.raises(RuntimeQueueFull if ending == 'cancel_cleanup' else asyncio.CancelledError):
                        await poll
                    driver.owner_call = owner_call
                    monkeypatch.setattr(owner, 'prepare_ready', original_prepare)
                else:
                    original_read = owner.admissions.read
                    def interrupted_read(*args, **kwargs):
                        result = original_read(*args, **kwargs)
                        if result.entry.state == 'provider_pending':
                            monkeypatch.setattr(owner.admissions, 'read', original_read)
                            raise OSError('final prepared receipt read failed')
                        return result
                    monkeypatch.setattr(owner.admissions, 'read', interrupted_read)
                    with pytest.raises(OSError, match='final prepared receipt read failed'):
                        await driver.poll()
                if ending.endswith('_cleanup'):
                    assert await owner_call(lambda: owner.runtime.pending_count) == 1
                else:
                    assert await owner_call(lambda: owner.runtime.pending_count) == 0
                assert calls == [] and driver._active == {}
                for _ in range(4):
                    await driver.poll()
                assert await owner_call(lambda: owner.runtime.pending_count) == 4
                assert len(driver._active) == 4
                return
            if ending == 'submit':
                original_submit = pool._executor.submit
                def fail_submit(*args, **kwargs):
                    monkeypatch.setattr(pool._executor, 'submit', original_submit)
                    raise RuntimeError('executor submit failed')
                monkeypatch.setattr(pool._executor, 'submit', fail_submit)
                with pytest.raises(RuntimeError, match='executor submit failed'):
                    await driver.poll()
                assert await owner_call(lambda: owner.runtime.pending_count) == 0
                original_revision = await owner_call(lambda: owner.admissions.read(keys[0]).entry.provider_revision)
                for _ in range(4):
                    await driver.poll()
                assert await owner_call(lambda: owner.admissions.read(keys[0]).entry.provider_revision) > original_revision
                return
            await driver.poll()
            for _ in range(100):
                if len(calls) == 4:
                    break
                await asyncio.sleep(.005)
            states = await owner_call(lambda: [(owner.admissions.read(key).entry.state,
                [owner.read_plan(key).after.stage, [row.reason for row in owner.read_plan(key).after.result.audit_records]] if owner.admissions.read(key).entry.commit_revision else '') for key in keys])
            assert len(calls) == 4 and owner_thread not in calls and get_ident() not in calls, states
            assert pool.acquire() is None
            assert await owner_call(lambda: owner.admissions.read(keys[4]).entry.state) == 'admitted'
            assert await owner_call(lambda: owner.runtime.pending_count) == 4
            assert await owner_call(lambda: all(owner.admissions.read(key).entry.state == 'provider_pending' for key in keys[:4]))
            if ending in {'complete', 'failure', 'owner'}:
                release.set()
                if ending == 'owner':
                    await asyncio.gather(*(asyncio.wrap_future(item[3]) for item in driver._active.values()))
                    async def unavailable(command):
                        raise OSError('owner unavailable')
                    driver.owner_call = unavailable
                    with pytest.raises(OSError, match='owner unavailable'):
                        await driver.poll()
                    assert len(driver._active) == 4
                    driver.owner_call = owner_call
                expected = ['failed' if ending == 'failure' else 'commit_started', *(['commit_started'] * 4)]
                for _ in range(100):
                    await driver.poll()
                    states = await owner_call(lambda: [owner.admissions.read(key).entry.state for key in keys])
                    if states == expected:
                        break
                    await asyncio.sleep(.005)
                assert states == expected
                if ending == 'failure':
                    assert await owner_call(lambda: owner.admissions.read(keys[0]).entry.transition.reason) == 'provider_failed:OSError'
                assert len(calls) == 5
                assert await owner_call(lambda: owner.runtime.pending_count) == 0
                return
            # 关闭不归还仍在 I/O 的槽；owner token 已失效，持久 pending 留给重启。
            await driver.close()
            assert pool.acquire() is None
            assert await owner_call(lambda: owner.runtime.pending_count) == 0
            assert await owner_call(lambda: owner.admissions.read(keys[0]).entry.state) == 'provider_pending'
        finally:
            release.set()
            await driver.close()
    try:
        asyncio.run(check())
    finally:
        release.set()
        pool._executor.shutdown(wait=True)
        execution.stop()
