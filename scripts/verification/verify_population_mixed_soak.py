"""真实 main/HTTP/WS 的混合墙钟采集；原始证据逐行落盘，不启动 Godot。"""
from __future__ import annotations

import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
from threading import Lock, get_ident
from time import perf_counter, process_time, sleep
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def heartbeat_record(execution, providers, probe, *, expected_at):
    from scripts.verification.population_benchmark_metrics import current_rss_bytes
    state = execution.snapshot()
    latest = probe.latest
    active = providers.active
    rss = current_rss_bytes()
    cpu = process_time()
    # latest先取稳定引用，时间在整次观察结束后采集，避免锁等待跨过Owner确认。
    return dict(type='heartbeat', expected_at=expected_at, at=perf_counter(), execution=state,
        provider_active=active, last_confirmed_tick=latest['sample']['confirmed_tick'] if latest else 0,
        rss_bytes=rss, cpu_seconds=cpu)


async def read_control(path, *, loader=None):
    # Windows的原子替换刚结束时可能仍有短期共享锁；只重试此类访问冲突，不吞坏JSON。
    async with asyncio.timeout(5):
        while True:
            try:
                return read(path) if loader is None else loader(path.read_text(encoding='utf-8'))
            except PermissionError:
                await asyncio.sleep(.02)


def process_resource_sample(host, kind, **fields):
    from scripts.verification.population_benchmark_metrics import current_rss_bytes
    return dict(type=kind, process_id=os.getpid(), at=perf_counter(), rss_bytes=current_rss_bytes(),
        cpu_seconds=process_time(), runtime_process=host.snapshot(), **fields)


async def wait_process_drain(host):
    """返回证明 IPC/发送已收口的完整观察，避免随后轮询占用额度使重采失真。"""
    async with asyncio.timeout(30):
        while True:
            sample = process_resource_sample(host, 'resources', phase='after_drain')
            state = sample['runtime_process']
            if state['status'] != 'ok':
                raise RuntimeError('mixed_process_failed_during_drain')
            if (all(state[key] == 0 for key in ('ipc_pending', 'pending_send', 'runtime_pending', 'transport_pending'))
                    and state['execution_credit']['current'] == 0):
                return sample
            await asyncio.sleep(.02)


def jsonl_writer(stream):
    lock = Lock()
    def record(row):
        raw = json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
        with lock:
            stream.write(raw)
            stream.flush()
    return record


def mixed_server_config(main):
    import uvicorn
    return uvicorn.Config(
        main.app,
        ws=main.RUNTIME_WEBSOCKET_PROTOCOL,
        access_log=False,
        log_level="warning",
        ws_per_message_deflate=False,
        # 慢消费者恢复由应用协议证明；legacy websockets 的并发 ping 不参与该故障配方。
        ws_ping_interval=None,
    )


def backend_environment(provider_mode, parent=None):
    from scripts.verification.population_godot_runner import child_environment
    parent = os.environ if parent is None else parent
    result = child_environment(parent)
    if provider_mode == 'live':
        allowed = {'DIALOGUE_MODE', 'CHARACTER_MODEL_PROVIDER_KIND', 'CHARACTER_MODEL_ENDPOINT', 'CHARACTER_MODEL_API_KEY',
            'CHARACTER_MODEL_MODEL', 'CHARACTER_MODEL_TIMEOUT_SECONDS', 'CHARACTER_MODEL_REQUIRE_ONLINE',
            'SIMING_LLM_MODE', 'SIMING_LLM_API_KEY', 'SIMING_LLM_ENDPOINT', 'SIMING_LLM_MODEL',
            'SIMING_LLM_TIMEOUT_SECONDS', 'SIMING_LLM_ROUTES_JSON', 'SIMING_LLM_PROVIDER_ORDER', 'SIMING_HEAVENLY_MODE'}
        result.update({key: value for key, value in parent.items() if key in allowed})
    return result


def drain_state(main, publisher):
    """owner截面点查真实待办索引和尚未结束的认知，不扫描历史。"""
    driver = main._population_runtime_driver
    due = sum(1 for _, obligation, tick, _ in driver.world_runtime._population_due_index.export_entries()
        if obligation.startswith('projection:organization-window-due:') and tick <= driver.current_tick)
    pending = bool(main.gameplay_event_store.list_outbox(include_delivered=False, topic=publisher.DOMAIN_TOPIC, limit=1))
    character, siming = main._character_cognition_driver, main._siming_cognition_driver
    if character is None or siming is None:
        raise ValueError('mixed_cognition_drain_unavailable')
    return dict(confirmed_tick=driver.current_tick, organization_due_count=due, domain_outbox_pending=pending,
        b1_drained=due == 0 and not pending,
        character_admission_pending=bool(character.coordinator.admissions.list_pending(limit=1)),
        siming_admission_pending=bool(siming.coordinator.admissions.list_pending_all(limit=1).entries),
        character_activation_handles=len(character._handles),
        character_continuations=len(main.character_agent_runtime.pending_cognition_jobs()),
        siming_continuations=siming.coordinator.runtime.pending_count,
        transient_owner_turns=len(main._transient_cognition_turns),
        cognition_output_pending=sum(sink.pending for sink in main._cognition_output_routes.connections.values()),
        dialogue_turns=len(main._dialogue_coordinator._pending) if main._dialogue_coordinator else 0)


def drain_loop_state(main):
    """loop拥有的任务只在loop读取；模型刚返回但尚未回owner也属于未排空。"""
    return dict(character_workers=len(main._character_cognition_driver._active),
        siming_workers=len(main._siming_cognition_driver._active),
        siming_unsubmitted=len(main._siming_cognition_driver._unsubmitted),
        transient_tasks=sum(not task.done() for task in main._transient_cognition_tasks))


def drain_complete(state):
    counters = ('character_activation_handles', 'character_continuations', 'siming_continuations',
        'transient_owner_turns', 'dialogue_turns', 'character_workers', 'siming_workers',
        'siming_unsubmitted', 'transient_tasks', 'cognition_output_pending', 'provider_active')
    return (state.get('b1_drained') is True and state.get('population_stopped') is True
        and state.get('character_admission_pending') is False and state.get('siming_admission_pending') is False
        and all(type(state.get(key)) is int and state[key] == 0 for key in counters))


def mixed_owner_child(commands, controls, results, notifications, settings_json):
    """原混合窗口、provider、故障及尾部排空均留在原 spawn owner。"""
    from app import main
    from app.services.runtime_process import runtime_child_main
    from scripts.verification.population_mixed_backend import install_mixed_fixtures, MixedWindowProbe, hold_sqlite_busy
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.population_mixed_load import MixedLoadSchedule, MixedLoadRunner
    from scripts.verification.population_mixed_fixture import prepare_conflict_fixture
    from scripts.verification.population_mixed_provider import MixedProviderProbe
    from scripts.verification.verify_population_service_isolation import until, install_writer_probes
    from app.services.runtime_execution import RuntimeExecution
    directory = Path(os.environ["PARALLS_MIXED_PROBE_DIRECTORY"])
    config = read(directory / "run.json")
    actors = read(directory / "roster.json")["actor_ids"]
    with ExitStack() as stack, (directory / "server.jsonl").open("w", encoding="utf-8") as output:
        install_mixed_fixtures(main, stack)
        meter = None
        if config.get("capacity_metrics") is True:
            from scripts.verification.population_benchmark_metrics import SqliteReadMeter
            meter = stack.enter_context(SqliteReadMeter())
        raw_record = jsonl_writer(output)
        def record(row):
            raw_record(dict(row, process_id=os.getpid()))
        schedule = MixedLoadSchedule(len(actors), config["seed"], config["mode"])
        windows = config["seconds"] * 1000 // schedule.window_ms
        def window_record(row):
            if row['type'] == 'window':
                row['phase'] = 'measurement' if row['target_tick'] <= windows else 'drain'
            record(row)
        probe = MixedWindowProbe(main, schedule, config["seconds"], window_record)
        probe.install(stack)
        providers = MixedProviderProbe(record)
        providers.install(stack)
        counters = dict(writer_calls={}, owner_threads=set(), mutation_threads=set(), max_writers=0, active_writers={})
        counter_lock = Lock()
        def writer(name, original):
            def invoke(*args, **kwargs):
                if probe.origin is None:
                    return original(*args, **kwargs)
                tid = get_ident()
                with counter_lock:
                    counters["mutation_threads"].add((os.getpid(), tid))
                    counters["writer_calls"][name] = counters["writer_calls"].get(name, 0) + 1
                    active = counters["active_writers"]
                    active[tid] = active.get(tid, 0) + 1
                    counters["max_writers"] = max(counters["max_writers"], len(active))
                try:
                    return original(*args, **kwargs)
                finally:
                    with counter_lock:
                        active[tid] -= 1
                        if not active[tid]:
                            del active[tid]
            return invoke
        boundaries = install_writer_probes(stack, writer)
        execute = RuntimeExecution._execute
        def owner(instance, *args, **kwargs):
            if probe.origin is not None:
                with counter_lock:
                    counters["owner_threads"].add((os.getpid(), get_ident()))
            return execute(instance, *args, **kwargs)
        stack.enter_context(patch.object(RuntimeExecution, "_execute", owner))
        start_population = main.start_population_runtime
        stack.enter_context(patch.object(main, "start_population_runtime", lambda: None))

        async def conflict(event):
            def command():
                from dataclasses import asdict
                result = prepare_conflict_fixture(store=main.gameplay_event_store,
                    packages=main.production_package_registry, policy_registry=main.production_social_policy_registry,
                    profiles=main.character_agent_runtime._profile_registry, actors=("char_b", "char_c"),
                    key=event.transaction_id + ":b2")
                return [asdict(row) for row in result]
            result = await asyncio.wrap_future(main.runtime_execution.submit(command))
            record(dict(type="b2_fixture", key=event.transaction_id, at=perf_counter(), sources=result))
            return dict(sources=result)
        busy_task = None
        async def busy(event):
            nonlocal busy_task
            if busy_task is not None and not busy_task.done():
                raise ValueError("mixed_sqlite_fault_overlap")
            busy_task = asyncio.create_task(hold_sqlite_busy(main.gameplay_event_store._snapshot_path))
            result = await asyncio.shield(busy_task)
            record(dict(type="sqlite_busy", key=event.transaction_id, **result))
            return result
        async def released(event):
            if busy_task is None:
                raise ValueError("mixed_sqlite_fault_missing")
            return await asyncio.shield(busy_task)
        async def timeout(event):
            providers.arm_timeout(event.transaction_id)
            return dict(armed=True)

        tasks, errors = [], []
        observer = None
        original_startup = main._start_population_runtime_on_startup
        original_shutdown = main._stop_population_runtime_on_shutdown

        async def observe():
            nonlocal tasks
            try:
                await asyncio.wrap_future(main.runtime_execution.submit(probe.attach))
                from scripts.verification.population_mixed_load import MixedLoadEvent
                await conflict(MixedLoadEvent(0, "initial_b2", 0, f"mixed:{len(actors)}:{config['seed']}:{config['mode']}:initial"))
                write_json(directory / "owner-ready.json", dict(owner_pid=os.getpid(),
                    population=len(actors), mode=main._population_runtime_driver.world_runtime.mode.model_dump(mode="json")))
                while not (directory / "start").exists():
                    if (directory / "stop").exists():
                        raise RuntimeError("mixed_backend_exited_before_start")
                    await asyncio.sleep(.02)
                interval = await read_control(directory / "start")
                origin, end = interval["origin"], interval["load_end"]
                if end != origin + config["seconds"]:
                    raise ValueError("mixed_interval_invalid")
                probe.origin = origin
                async def heartbeat():
                    for ordinal in range(1, config["seconds"] // 10 + 1):
                        expected = origin + ordinal * 10
                        await until(expected)
                        record(heartbeat_record(main.runtime_execution, providers, probe, expected_at=expected))
                backend_load = MixedLoadRunner(dict(siming_model=conflict, provider_timeout=timeout,
                    sqlite_busy=busy, sqlite_release=released), drain_seconds=30)
                tasks = [asyncio.create_task(heartbeat())]
                # 短测未到60秒没有server schedule输入，仍保留初始真实source。
                if config["seconds"] >= 60:
                    tasks.append(asyncio.create_task(backend_load.run(config["seconds"], schedule, origin=origin)))
                await until(origin)
                if meter is not None:
                    record(dict(type='capacity_resources', phase='start', at=perf_counter(),
                        cpu_seconds=process_time(), sqlite=meter.snapshot()))
                start_population()
                while not (directory / "stop").exists():
                    failure = main.get_population_runtime_failure()
                    if failure is not None:
                        raise RuntimeError("mixed_population_runtime_failed")
                    await asyncio.sleep(.02)
                early = perf_counter() < end
                if early:
                    for task in tasks:
                        task.cancel()
                for task in tasks:
                    try:
                        result = await task
                    except asyncio.CancelledError:
                        if not early:
                            raise
                        result = None
                    if result is not None:
                        write_json(directory / "server-requests.json", result)
                if config['seconds'] < 60 and not early:
                    write_json(directory / 'server-requests.json', dict(origin=origin, load_end=end,
                        finished_at=perf_counter(), offered=0, dispatched=0, failed=0, peak_in_flight=0, requests=[]))
                drain = dict(proven=False, b1_drained=False, limitations=['load_stopped_early'])
                population_stopped = False
                if not early:
                    # backend来源及客户端请求都结束后，再等至少一个真实public窗处理尾部来源。
                    cut = await asyncio.wrap_future(main.runtime_execution.submit(lambda: main._population_runtime_driver.current_tick))
                    deadline = perf_counter() + 30
                    while True:
                        if main.get_population_runtime_failure() is not None:
                            raise RuntimeError('mixed_population_runtime_failed_during_drain')
                        if probe.publisher is not None:
                            drain = await asyncio.wrap_future(main.runtime_execution.submit(lambda: drain_state(main, probe.publisher)))
                            if (not population_stopped and drain['confirmed_tick'] >= max(windows, cut+1)
                                    and drain['b1_drained']):
                                # 先完成输入尾部的public/B1窗，再停新窗口；认知driver继续处理已有义务。
                                main._population_runtime_stop_event.set()
                                await asyncio.wait_for(asyncio.shield(main._population_runtime_task), 30)
                                population_stopped = True
                                continue  # 停窗可能完成最后一个已入队窗口，重读其真实末态。
                            drain.update(drain_loop_state(main), required_tick=max(windows, cut+1),
                                provider_active=providers.active, population_stopped=population_stopped)
                            drain['proven'] = drain_complete(drain)
                            drain['limitations'] = [] if drain['proven'] else ['runtime_work_pending']
                            record(dict(type='drain', at=perf_counter(), **drain))
                            if drain['proven']:
                                break
                        if perf_counter() >= deadline:
                            drain['timed_out'] = True
                            break
                        await asyncio.sleep(.05)
                if not population_stopped:
                    main._population_runtime_stop_event.set()
                    await asyncio.wait_for(asyncio.shield(main._population_runtime_task), 30)
                if meter is not None:
                    record(dict(type='capacity_resources', phase='after_drain', at=perf_counter(),
                        cpu_seconds=process_time(), sqlite=meter.snapshot()))
                def final():
                    driver = main._population_runtime_driver
                    world = driver.world_runtime
                    recovery = world.export_recovery_state()
                    return dict(confirmed_tick=driver.current_tick, state_digest=recovery['state_digest'],
                        recovery_state=recovery, mode=world.mode.model_dump(mode='json'), drain=drain,
                        authority_head=main.gameplay_event_store.get_last_global_sequence())
                write_json(directory / "final-state.json", await asyncio.wrap_future(main.runtime_execution.submit(final)))

            except BaseException as error:
                errors.append(type(error).__name__)
                raise
            finally:
                try:
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    if busy_task is not None:
                        await asyncio.shield(busy_task)
                finally:
                    write_json(directory / "owner-drained.json", dict(owner_pid=os.getpid(), errors=errors))

        async def startup():
            nonlocal observer
            await original_startup()
            observer = asyncio.create_task(observe())

        async def shutdown():
            try:
                try:
                    if observer is not None and not observer.done():
                        observer.cancel()
                    if observer is not None:
                        await observer
                finally:
                    await original_shutdown()
            except BaseException as error:
                errors.append(type(error).__name__)
                raise
            finally:
                with counter_lock:
                    summary = {key: sorted(value) if isinstance(value, set) else value for key, value in counters.items()}
                write_json(directory / "owner-observed.json", dict(**summary, owner_pid=os.getpid(),
                    writer_boundaries=boundaries, provider_peak_active=providers.peak_active,
                    provider_active=providers.active, pending_timeout=providers.timeout_key, errors=errors,
                    interval=dict(origin=probe.origin, load_end=probe.origin + config["seconds"]) if probe.origin is not None else None,
                    driver_origin=probe.driver_origin, provider_mode=config["provider_mode"]))

        stack.enter_context(patch.object(main, "_start_population_runtime_on_startup", startup))
        stack.enter_context(patch.object(main, "_stop_population_runtime_on_shutdown", shutdown))
        try:
            runtime_child_main(commands, controls, results, notifications, settings_json)
        finally:
            from app.services.process_qos import process_qos_snapshot
            write_json(directory / 'owner-qos.json', process_qos_snapshot())


async def backend(directory):
    from scripts.verification.population_mixed_backend import configure, merge_process_observations
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.verify_population_service_isolation import until, install_writer_probes
    from app.services import runtime_process
    import uvicorn
    config = read(directory / "run.json")
    parent = dict(parent_pid=os.getpid(), owner_pid=None, child_exit_code=None, errors=[], writer_calls={},
        population=config["population"], provider_mode=config["provider_mode"])
    async def owner_file(name):
        async with asyncio.timeout(config["seconds"] + 90 if name == "owner-drained.json" else 90):
            while not (directory / name).exists():
                if serving.done() or not host.process.is_alive():
                    raise RuntimeError("mixed_owner_exited")
                if name == "owner-ready.json" and (directory / "owner-drained.json").exists():
                    raise RuntimeError("mixed_owner_start_failed")
                await asyncio.sleep(.02)
        result = await read_control(directory / name)
        if result.get("errors") or result["owner_pid"] != host.process.pid:
            raise RuntimeError("mixed_owner_observation_failed")
        return result

    with ExitStack() as stack, (directory / "parent.jsonl").open("w", encoding="utf-8") as output:
        main, actors, secret = configure(directory, stack, mode=config["mode"], provider_mode=config["provider_mode"])
        record = jsonl_writer(output)
        counter_lock = Lock()
        def writer(name, original):
            def invoke(*args, **kwargs):
                with counter_lock:
                    parent["writer_calls"][name] = parent["writer_calls"].get(name, 0) + 1
                return original(*args, **kwargs)
            return invoke
        parent["writer_boundaries"] = install_writer_probes(stack, writer)
        stack.enter_context(patch.dict(os.environ, {"PARALLS_MIXED_PROBE_DIRECTORY": str(directory)}))
        stack.enter_context(patch.object(runtime_process, "CHILD_TARGET", mixed_owner_child))
        listener = stack.enter_context(socket.socket())
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        listener.setblocking(False)
        server = uvicorn.Server(mixed_server_config(main))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        host = heartbeat = None
        def sample(kind, **fields):
            record(process_resource_sample(host, kind, **fields))
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("mixed_backend_start_failed")
                await asyncio.sleep(.02)
            host = main.app.state.runtime_process
            parent["owner_pid"] = host.process.pid
            ready = await owner_file("owner-ready.json")
            if ready["population"] != len(actors):
                raise ValueError("mixed_owner_population_invalid")
            write_json(directory / "ready.json", dict(port=listener.getsockname()[1], secret=secret,
                population=len(actors), mode=ready["mode"]))
            while not (directory / "start").exists():
                if serving.done() or (directory / "stop").exists():
                    raise RuntimeError("mixed_backend_exited_before_start")
                await asyncio.sleep(.02)
            interval = await read_control(directory / "start")
            origin, end = interval["origin"], interval["load_end"]
            if end != origin + config["seconds"]:
                raise ValueError("mixed_interval_invalid")
            parent["interval"] = interval
            async def heartbeats():
                for ordinal in range(1, config["seconds"] // 10 + 1):
                    expected = origin + ordinal * 10
                    await until(expected)
                    sample("heartbeat", expected_at=expected)
            heartbeat = asyncio.create_task(heartbeats())
            await until(origin)
            sample("resources", phase="start")
            await owner_file("owner-drained.json")
            record(await wait_process_drain(host))
            early = perf_counter() < end
            if early:
                heartbeat.cancel()
            result, = await asyncio.gather(heartbeat, return_exceptions=True)
            if isinstance(result, BaseException) and not (early and isinstance(result, asyncio.CancelledError)):
                raise result
        except BaseException as error:
            parent["errors"].append(type(error).__name__)
            raise
        finally:
            if heartbeat is not None and not heartbeat.done():
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)
            server.should_exit = True
            try:
                await asyncio.wait_for(serving, 45)
            except BaseException as error:
                parent["errors"].append(type(error).__name__)
                raise
            finally:
                parent["child_exit_code"] = host.process.exitcode if host is not None else None
                lifecycle = getattr(server, "lifespan", None)
                parent["asgi_lifecycle"] = {key: getattr(lifecycle, key, None) for key in
                    ("startup_failed", "shutdown_failed", "error_occurred")}
                write_json(directory / 'parent-qos.json', main.app.state.process_qos)
                write_json(directory / "parent-observed.json", parent)
    owner = read(directory / "owner-observed.json")
    write_json(directory / "server.json", merge_process_observations(parent, owner, ready))


async def load(directory, config, shared_start=None):
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.population_mixed_load import MixedLoadSchedule, MixedLoadRunner
    from scripts.verification.population_mixed_transport import MixedLoadHttpWs
    from scripts.verification.population_mixed_faults import MixedMirrorFaultClient
    ready = await read_control(directory / "ready.json")
    with (directory / "responses.jsonl").open("w", encoding="utf-8") as stream:
        record = jsonl_writer(stream)
        transport = MixedLoadHttpWs(http_url=f"http://127.0.0.1:{ready['port']}", launcher_secret=ready["secret"],
            launch_profile_ref="population-mixed", record=record, timeout_seconds=40)
        actors = read(directory / "roster.json")["actor_ids"]
        fault = MixedMirrorFaultClient(transport, {"character:" + actor for actor in actors[:100]})
        try:
            if shared_start is None:
                origin = perf_counter() + .2
                interval = dict(origin=origin, load_end=origin+config['seconds'])
            else:
                # 所有局都已ready才由父协调器一次发布共同起点；不改真实时钟。
                async with asyncio.timeout(150):
                    while not shared_start.exists():
                        await asyncio.sleep(.02)
                    interval = await read_control(shared_start)
                from scripts.verification.population_mixed_evidence import number
                if interval.get('abort'):
                    raise ValueError('mixed_shared_start_aborted')
                origin = number(interval['origin'], minimum=perf_counter())
                if interval != dict(origin=origin, load_end=origin+config['seconds']):
                    raise ValueError('mixed_shared_interval_invalid')
            write_json(directory / 'start', interval)
            result = await MixedLoadRunner({**transport.handlers(), **fault.handlers()}, drain_seconds=45).run(
                config["seconds"], MixedLoadSchedule(len(actors), config["seed"], config["mode"]), origin=origin)
            write_json(directory / "client.json", result)
            return result
        finally:
            await fault.close()


async def load_while_backend_alive(directory, config, process, shared_start=None):
    """客户端负载只在本轮自有后端存活时继续。"""
    task = asyncio.create_task(load(directory, config, shared_start))
    await asyncio.sleep(0)
    try:
        while not task.done():
            if process.poll() is not None:
                raise RuntimeError("mixed_backend_exited_during_load")
            await asyncio.wait((task,), timeout=.05)
        return task.result()
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def collect(directory, *, population, seed, seconds, mode, provider_mode, shared_start=None, capacity_metrics=False):
    from scripts.verification.population_mixed_load import MixedLoadSchedule
    # 直接调用和 CLI 使用同一配置约束；非法输入不能先启动子进程。
    schedule = MixedLoadSchedule(population, seed, mode)
    next(schedule.events(seconds))
    if population not in (100, 1000, 10000) or provider_mode not in {"live", "local_probe"}:
        raise ValueError("mixed_collection_configuration_invalid")
    if directory.exists():
        raise ValueError("mixed_output_must_be_new")
    directory.mkdir(parents=True, exist_ok=False)
    from scripts.verification.population_process_qos import recorded_high_qos
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.verify_population_service_isolation import raw_artifacts
    try:
        with recorded_high_qos(directory / 'collector-qos.json'):
            result = _collect_with_policy(directory, population=population, seed=seed, seconds=seconds, mode=mode, provider_mode=provider_mode, shared_start=shared_start, capacity_metrics=capacity_metrics)
        return result
    finally:
        path = directory / 'manifest.json'
        if path.exists():
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if sys.exc_info()[0] is not None:
                manifest.update(passed=False, status='failed')
                manifest.setdefault('errors', []).append('collection_scope:' + sys.exc_info()[0].__name__)
            manifest['raw_artifacts'] = raw_artifacts(directory)
            write_json(path, manifest)
            if 'result' in locals():
                result.update(manifest)


def _collect_with_policy(directory, *, population, seed, seconds, mode, provider_mode, shared_start=None, capacity_metrics=False):
    from scripts.verification.population_godot_runner import source_manifest, write_json
    from scripts.verification.verify_population_runtime_correctness import environment
    from scripts.verification.verify_population_service_isolation import raw_artifacts
    (directory / "state").mkdir()
    config = dict(population=population, seed=seed, seconds=seconds, mode=mode, provider_mode=provider_mode)
    if capacity_metrics:
        config['capacity_metrics'] = True
    write_json(directory / "run.json", config)
    write_json(directory / "roster.json", dict(actor_ids=["char_a", "char_b", "char_c",
        *[f"resident_{i:05d}" for i in range(population-3)]]))
    source = source_manifest()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True).splitlines()
    # 本地诊断可采集未提交实现；正式复验必须拒绝脏源码，而不能只相信 HEAD。
    dirty = sorted(set(changed + untracked).intersection(source["files"]))
    started_at = datetime.now(timezone.utc).isoformat()
    machine = environment()
    machine.update(provider_mode=provider_mode, runner_name=os.environ.get("RUNNER_NAME"),
        runner_environment=os.environ.get("RUNNER_ENVIRONMENT"))
    errors, client = [], None
    endpoint = None
    with (directory / "process.log").open("w", encoding="utf-8") as stream:
        from scripts.verification.population_python_process import python_process
        command, child_env = python_process([__file__, "--backend-child", directory], backend_environment(provider_mode))
        process = subprocess.Popen(command,
            cwd=ROOT, env=child_env, stdout=stream, stderr=subprocess.STDOUT)
        try:
            deadline = perf_counter() + 120
            while not (directory / "ready.json").exists():
                if process.poll() is not None or perf_counter() >= deadline:
                    raise RuntimeError("mixed_backend_not_ready")
                sleep(.05)
            endpoint = dict(host='127.0.0.1', port=read(directory / 'ready.json')['port'])
            if shared_start is not None:
                write_json(directory / 'prepared.json', dict(backend_pid=process.pid, endpoint=endpoint))
            client = asyncio.run(load_while_backend_alive(
                directory, config, process, shared_start
            ))
        except BaseException as error:
            errors.append(type(error).__name__)
        finally:
            (directory / "stop").touch()
            try:
                process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                errors.append("mixed_owned_backend_shutdown_timeout")
            (directory / "ready.json").unlink(missing_ok=True)
    if process.returncode == 0:
        # 两个原库均已停止写入；证明导出不进入被测服务的计时和RSS。
        try:
            from scripts.verification.population_mixed_authority import export_gameplay
            from scripts.verification.population_mixed_cognition import export_character
            from scripts.verification.population_mixed_siming import export_siming
            export_gameplay(directory / 'state/graph.sqlite3.gameplay.json', directory / 'authority.jsonl')
            export_character(directory / 'state/graph.sqlite3', directory / 'character.jsonl')
            export_siming(directory / 'state/graph.sqlite3', directory / 'siming.jsonl')
        except (OSError, ValueError, KeyError, sqlite3.Error) as error:
            errors.append('proof_export:' + type(error).__name__)
    # 在完整离线门禁复验前，采集成功也不能标记正式通过。
    manifest = dict(schema_version=1, profile="population-mixed-soak", base_commit=revision, source=source,
        config=config, backend_exit_code=process.returncode, errors=errors, godot_status="godot_unverified",
        source_dirty_paths=dirty, environment=machine, started_at=started_at,
        finished_at=datetime.now(timezone.utc).isoformat(), backend_pid=process.pid,
        endpoint=endpoint,
        collection_finished=client is not None and process.returncode == 0 and not errors,
        passed=False, verification_status="offline_verification_required")
    if source_manifest() != source:
        manifest["errors"].append("source_changed_during_collection")
        manifest["collection_finished"] = False
    manifest["raw_artifacts"] = raw_artifacts(directory)
    write_json(directory / "manifest.json", manifest)
    return manifest


def verify_artifacts(directory, *, expected_commit):
    from scripts.verification.population_mixed_matrix import verify_matrix
    return verify_matrix(directory, expected_commit=expected_commit, kind='soak')


def verify_short_artifacts(directory, *, expected_commit):
    from scripts.verification.population_mixed_matrix import verify_matrix
    return verify_matrix(directory, expected_commit=expected_commit, kind='short')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend-child", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--collect", type=Path)
    parser.add_argument("--population", type=int, choices=(100, 1000, 10000), default=100)
    parser.add_argument("--seed", type=int, default=31)
    parser.add_argument("--seconds", type=int, default=1800)
    parser.add_argument("--mode", choices=("one_x", "ten_x"), default="one_x")
    parser.add_argument("--provider-mode", choices=("live", "local_probe"), default="live")
    args = parser.parse_args()
    if args.backend_child:
        asyncio.run(backend(args.backend_child.resolve()))
        return 0
    if args.collect is None or args.seconds <= 0 or args.seed < 0:
        parser.error("new --collect directory, positive --seconds and nonnegative --seed required")
    result = collect(args.collect.resolve(), population=args.population, seed=args.seed, seconds=args.seconds,
        mode=args.mode, provider_mode=args.provider_mode)
    print(json.dumps({key: result[key] for key in ("collection_finished", "passed", "verification_status", "errors")}, ensure_ascii=False))
    return 0 if result["collection_finished"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
