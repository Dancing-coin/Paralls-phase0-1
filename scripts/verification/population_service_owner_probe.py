"""服务门禁的真实 owner 子进程探针；启动原 runtime，不增加生产诊断入口。"""
import asyncio
from contextlib import ExitStack
import os
from pathlib import Path
import sys
from threading import Lock, get_ident
from time import perf_counter, sleep
from unittest.mock import patch


def service_owner_child(commands, controls, results, notifications, settings_json):
    from app import main
    from app.character_agent.gateway.model_provider import CharacterModelProvider
    from app.services.runtime_execution import RuntimeExecution
    from app.services.runtime_process import runtime_child_main
    from app.services.siming_llm_provider import DisabledSimingLlmCandidateProvider
    from scripts.verification.verify_population_service_isolation import install_writer_probes, until
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.verify_population_mixed_soak import read_control

    # spawn 保留原验证器 argv；不用新环境开关或将私有路径写入业务命令。
    directory = Path(sys.argv[sys.argv.index('--backend-child') + 1])
    observed = dict(owner_pid=os.getpid(), window_ms=[], window_started_at=[],
        max_lag_windows=0, final_backlog=0, owner_queue_peak=0, max_writers=0,
        provider_calls=0, provider_max_active=0, windows_during_provider=0,
        writer_calls={}, errors=[])
    owners, writers, providers = set(), set(), set()
    active_writers = {}
    provider_active = 0
    measuring = False
    measurement_task = None
    lock = Lock()

    def writer(name, original):
        def invoke(*args, **kwargs):
            if not measuring:
                return original(*args, **kwargs)
            identity = (os.getpid(), get_ident())
            with lock:
                writers.add(identity)
                observed['writer_calls'][name] = observed['writer_calls'].get(name, 0) + 1
                active_writers[identity] = active_writers.get(identity, 0) + 1
                observed['max_writers'] = max(observed['max_writers'], len(active_writers))
            try:
                return original(*args, **kwargs)
            finally:
                with lock:
                    active_writers[identity] -= 1
                    if not active_writers[identity]:
                        del active_writers[identity]
        return invoke

    def provider_enter():
        nonlocal provider_active
        with lock:
            providers.add((os.getpid(), get_ident()))
            provider_active += 1
            observed['provider_calls'] += 1
            observed['provider_max_active'] = max(observed['provider_max_active'], provider_active)
        sleep(1.)

    def provider_exit():
        nonlocal provider_active
        with lock:
            provider_active -= 1

    def slow(original):
        def invoke(*args, **kwargs):
            provider_enter()
            try:
                return original(*args, **kwargs)
            finally:
                provider_exit()
        return invoke

    original_stream = CharacterModelProvider.stream_dialogue
    def stream(*args, **kwargs):
        provider_enter()
        try:
            yield from original_stream(*args, **kwargs)
        finally:
            provider_exit()

    original_execute = RuntimeExecution._execute
    def execute(instance, *args, **kwargs):
        if measuring:
            owners.add((os.getpid(), get_ident()))
            observed['owner_queue_peak'] = max(observed['owner_queue_peak'], instance.snapshot()['queue_depth'])
        return original_execute(instance, *args, **kwargs)

    original_startup = main._start_population_runtime_on_startup
    original_shutdown = main._stop_population_runtime_on_shutdown
    start_population = main.start_population_runtime

    async def measure():
        nonlocal measuring
        try:
            driver = main._population_runtime_driver
            if driver is None or driver.window_size != 1 or driver.current_tick != 0:
                raise ValueError('service_fixture_driver_invalid')
            observed.update(window_size=driver.window_size, population=len(driver.world_runtime.roster.actor_ids))
            write_json(directory / 'owner-ready.json', observed)
            while not (directory / 'start').exists():
                await asyncio.sleep(.02)
            interval = await read_control(directory / 'start')
            origin, end = interval['load_started_at'], interval['load_ended_at']
            if end <= origin:
                raise ValueError('service_load_interval_invalid')
            observed.update(interval)
            original_tick = driver.tick
            def tick(target):
                began = perf_counter()
                with lock:
                    waiting = provider_active > 0
                result = original_tick(target)
                observed['window_started_at'].append(began)
                observed['window_ms'].append((perf_counter() - began) * 1000)
                if origin <= began < end:
                    observed['max_lag_windows'] = max(observed['max_lag_windows'],
                        int(min(perf_counter(), end) - origin) - driver.current_tick)
                    if waiting and result.published_cadence_ids:
                        observed['windows_during_provider'] += 1
                if result.rejected_windows:
                    observed['errors'].append('population_window_rejected')
                return result
            await asyncio.wrap_future(main.runtime_execution.submit(lambda: setattr(driver, 'tick', tick)))
            measuring = True
            await until(origin)
            start_population()
            while perf_counter() < end and not (directory / 'stop').exists():
                await asyncio.sleep(.02)
            observed['load_end_observed_at'] = perf_counter()
            if observed['load_end_observed_at'] < end:
                observed['errors'].append('service_load_interrupted')
            observed['final_backlog'] = max(0, int(min(perf_counter(), end) - origin) - driver.current_tick)
            while not (directory / 'stop').exists():
                await asyncio.sleep(.02)
            main._population_runtime_stop_event.set()
            await asyncio.wait_for(asyncio.shield(main._population_runtime_task), 30)
        except asyncio.CancelledError:
            observed['errors'].append('service_owner_measurement_cancelled')
            raise
        except Exception as error:
            observed['errors'].append(type(error).__name__)
        finally:
            measuring = False
            observed.update(owner_threads=sorted(owners), mutation_threads=sorted(writers),
                provider_threads=sorted(providers), provider_mode='controlled_local_one_second_delay')
            write_json(directory / 'owner-observed.json', observed)

    async def startup():
        nonlocal measurement_task
        await original_startup()
        measurement_task = asyncio.create_task(measure())

    async def shutdown():
        if measurement_task is not None and not measurement_task.done():
            measurement_task.cancel()
        if measurement_task is not None:
            await asyncio.gather(measurement_task, return_exceptions=True)
        await original_shutdown()

    with ExitStack() as stack:
        observed['writer_boundaries'] = install_writer_probes(stack, writer)
        stack.enter_context(patch.object(RuntimeExecution, '_execute', execute))
        stack.enter_context(patch.object(CharacterModelProvider, 'complete', slow(CharacterModelProvider.complete)))
        stack.enter_context(patch.object(CharacterModelProvider, 'stream_dialogue', stream))
        for method in ('generate_candidates', 'generate_adaptive_bridge_proposals'):
            stack.enter_context(patch.object(DisabledSimingLlmCandidateProvider, method,
                slow(getattr(DisabledSimingLlmCandidateProvider, method))))
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        stack.enter_context(patch.object(main, '_start_population_runtime_on_startup', startup))
        stack.enter_context(patch.object(main, '_stop_population_runtime_on_shutdown', shutdown))
        try:
            runtime_child_main(commands, controls, results, notifications, settings_json)
        finally:
            from app.services.process_qos import process_qos_snapshot
            write_json(directory / 'owner-qos.json', process_qos_snapshot())
