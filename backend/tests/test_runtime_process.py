"""真实 spawn 生命周期；底座证据不代替完整 transport 服务门禁。"""
import asyncio
import os

import pytest

from app.config import Settings
from app.services.runtime_process import RuntimeProcess, RuntimeProcessError


def command_channel(queue):
    import multiprocessing
    from app.services.runtime_process import RuntimeCommandChannel
    return RuntimeCommandChannel(queue, multiprocessing.get_context("spawn").BoundedSemaphore(128))


def settings_json():
    return Settings(heavenly_graph_path=':memory:', dialogue_mode='stub',
        character_model_provider_kind='local', siming_llm_mode='disabled').model_dump_json()


def gc_observing_child(commands, controls, results, notifications, settings_json):
    import gc
    import json
    from pathlib import Path
    from app import main
    from app.services.runtime_process import runtime_child_main
    original = main._start_population_runtime_on_startup
    # 非默认高代阈值用于证明生产入口只调整第零代。
    gc.set_threshold(700, 13, 17)

    async def start():
        path = Settings.model_validate_json(settings_json).heavenly_graph_path
        Path(str(path) + '.gc.json').write_text(json.dumps({
            'threshold': gc.get_threshold(), 'enabled': gc.isenabled(), 'pid': os.getpid(),
            'qos': __import__('app.services.process_qos', fromlist=['process_qos_snapshot']).process_qos_snapshot(),
        }), encoding='utf-8')
        await original()

    main._start_population_runtime_on_startup = start
    runtime_child_main(commands, controls, results, notifications, settings_json)
    from app.services.process_qos import process_qos_snapshot
    path = Settings.model_validate_json(settings_json).heavenly_graph_path
    Path(str(path) + '.qos-restored.json').write_text(json.dumps(process_qos_snapshot()), encoding='utf-8')


def test_real_spawn_gc_threshold_is_child_only_and_preserves_older_generations(monkeypatch, tmp_path):
    import gc
    import json
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', gc_observing_child)
    before = (gc.get_threshold(), gc.isenabled())
    settings = Settings.model_validate_json(settings_json())
    settings.heavenly_graph_path = str(tmp_path / 'graph.sqlite3')

    async def run():
        host = RuntimeProcess(settings.model_dump_json())
        try:
            await asyncio.wait_for(host.start(), 20)
            observed = json.loads((tmp_path / 'graph.sqlite3.gc.json').read_text(encoding='utf-8'))
            policy = observed.pop('qos')
            assert policy['pid'] == host.process.pid
            if os.name == 'nt':
                assert policy['applied'][1] & 1 and not policy['applied'][2] & 1
            assert observed == {'threshold': [21000, 13, 17], 'enabled': True, 'pid': host.process.pid}
            assert host.process.pid != os.getpid()
        finally:
            await host.close()
        assert host.process.exitcode == 0

    asyncio.run(run())
    restored = json.loads((tmp_path / 'graph.sqlite3.qos-restored.json').read_text(encoding='utf-8'))
    assert restored['restored'] == restored['before']
    assert (gc.get_threshold(), gc.isenabled()) == before


def test_real_spawn_owns_runtime_and_stops_without_parent_runtime():
    async def run():
        host = RuntimeProcess(settings_json())
        try:
            await asyncio.wait_for(host.start(), 20)
            snapshot = host.snapshot()
            assert snapshot['child_pid'] != os.getpid()
            assert snapshot['status'] == 'ok'
            result = await host.request('runtime.snapshot', {})
            assert result['runtime_execution']['state'] == 'running'
            with pytest.raises(RuntimeProcessError, match='unknown_command'):
                await host.request('arbitrary.python', {'attribute': 'runtime_execution'})
            with pytest.raises((TypeError, ValueError)):
                await host.request('runtime.snapshot', {'callback': lambda: None})
            assert host.pending_count == 0
        finally:
            await host.close()
        assert host.process.exitcode == 0
        assert host.snapshot()['status'] == 'unhealthy'
        await host.close()
    asyncio.run(run())


def test_child_exit_fails_pending_and_cached_health_without_restarting():
    async def run():
        host = RuntimeProcess(settings_json())
        await asyncio.wait_for(host.start(), 20)
        pid = host.process.pid
        try:
            host.process.terminate()
            await asyncio.to_thread(host.process.join, 5)
            assert host.snapshot()['status'] == 'unhealthy'
            with pytest.raises(RuntimeProcessError):
                await host.request('runtime.snapshot', {})
            assert host.process.pid == pid
        finally:
            await host.close()
    asyncio.run(run())



def gated_child(commands, controls, results, notifications, settings_json):
    """仅验证 IPC 关联上限的可控 child；真实装配由上面独立 spawn 测试覆盖。"""
    import json
    from queue import Empty
    commands = commands.queue
    def emit(kind, **payload):
        results.put(json.dumps(dict(schema=1, kind=kind, generation='credit-test', **payload)))
    emit('ready', health={'status': 'ok', 'runtime_execution': {'state': 'running'}})
    control = json.loads(controls.get())
    if control['kind'] == 'release':
        while True:
            try:
                control = json.loads(controls.get_nowait())
                if control['kind'] == 'shutdown':
                    break
            except Empty:
                pass
            try:
                command = json.loads(commands.get(timeout=.02))
                emit('result', sequence=command['sequence'], value={})
            except Empty:
                pass
    emit('stopped')


def test_pending_correlation_covers_cancelled_waiter_until_original_result(monkeypatch):
    import json
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', gated_child)
    async def run():
        host = RuntimeProcess(settings_json())
        await host.start()
        tasks = [asyncio.create_task(host.request('runtime.snapshot', {})) for _ in range(128)]
        try:
            for _ in range(100):
                if host.pending_count == 128:
                    break
                await asyncio.sleep(.01)
            assert host.pending_count == 128
            tasks[0].cancel()
            await asyncio.gather(tasks[0], return_exceptions=True)
            assert host.pending_count == 128
            with pytest.raises(RuntimeProcessError, match='queue_full'):
                await host.request('runtime.snapshot', {})
            host._controls.put_nowait(json.dumps(dict(schema=1, kind='release', generation='credit-test')))
            await asyncio.wait_for(asyncio.gather(*tasks[1:]), 5)
            assert host.pending_count == 0
        finally:
            await asyncio.gather(host.close(), host.close())
        assert host.process.exitcode == 0
    asyncio.run(run())


def test_invalid_startup_configuration_does_not_leave_child_running():
    async def run():
        host = RuntimeProcess('{invalid')
        with pytest.raises(RuntimeProcessError):
            await asyncio.wait_for(host.start(), 10)
        assert not host.process.is_alive()
        await host.close()
    asyncio.run(run())



def test_actual_child_death_resolves_original_pending_once(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', gated_child)
    async def run():
        host = RuntimeProcess(settings_json())
        await host.start()
        pending = asyncio.create_task(host.request('runtime.snapshot', {}))
        await asyncio.sleep(.02)
        assert host.pending_count == 1
        host.process.terminate()
        with pytest.raises(RuntimeProcessError, match='child_exited'):
            await asyncio.wait_for(pending, 5)
        assert host.pending_count == 0
        await host.close()
    asyncio.run(run())


@pytest.mark.parametrize('raw', [object(), '[]', '{"schema":true}', '{"schema":1,"value":NaN}'])
def test_ipc_rejects_non_json_or_noncanonical_schema(raw):
    from app.services.runtime_process import _decode
    with pytest.raises((TypeError, ValueError)):
        _decode(raw)

class ControlledProcess:
    pid = 123
    exitcode = None
    def __init__(self, refuses_termination=False):
        self.alive = True
        self.refuses_termination = refuses_termination
    def is_alive(self):
        return self.alive
    def terminate(self):
        if not self.refuses_termination:
            self.alive = False
    def join(self, timeout):
        pass


def test_shutdown_deadline_includes_full_control_queue(monkeypatch):
    import app.services.runtime_process as module
    original_wait_for = asyncio.wait_for
    async def short_wait(awaitable, timeout):
        return await original_wait_for(awaitable, min(timeout, .03))
    monkeypatch.setattr(module.asyncio, 'wait_for', short_wait)
    async def run():
        host = RuntimeProcess(settings_json())
        host.process = ControlledProcess()
        host._stopped = asyncio.get_running_loop().create_future()
        release = asyncio.Event()
        async def full_control(*args):
            await release.wait()
        monkeypatch.setattr(module, '_put', full_control)
        closing = asyncio.create_task(host.close())
        try:
            done, _ = await asyncio.wait([closing], timeout=.15)
            assert closing in done, '满 control 队列必须纳入原关闭期限'
            await closing
            assert not host.process.is_alive()
        finally:
            release.set()
            if not closing.done():
                host._stopped.set_result(None)
                host.process.alive = False
            await closing
    asyncio.run(run())


def test_failed_termination_retains_channels_and_allows_close_retry(monkeypatch):
    import app.services.runtime_process as module
    original_wait_for = asyncio.wait_for
    async def short_wait(awaitable, timeout):
        return await original_wait_for(awaitable, min(timeout, .03))
    monkeypatch.setattr(module.asyncio, 'wait_for', short_wait)
    async def run():
        host = RuntimeProcess(settings_json())
        host.process = ControlledProcess(refuses_termination=True)
        host._stopped = asyncio.get_running_loop().create_future()
        with pytest.raises(RuntimeProcessError, match='shutdown_incomplete'):
            await host.close()
        try:
            assert not host._closed
            assert not host._controls._closed
            assert host.snapshot()['status'] == 'unhealthy'
        finally:
            host.process.refuses_termination = False
            await host.close()
        assert not host.process.is_alive()
        assert host._closed
    asyncio.run(run())


def test_child_stopped_requires_original_owner_terminal(monkeypatch):
    from queue import Queue, Empty
    from threading import Event
    from app import main
    from app.services.runtime_execution import RuntimeExecution
    from app.services.runtime_process import _run_child, _decode, _encode
    async def run():
        release, entered, resource_closed = Event(), Event(), Event()
        execution = RuntimeExecution(on_stop=resource_closed.set)
        execution.submit(lambda: (entered.set(), release.wait(5)))
        assert entered.wait(1)
        async def startup():
            pass
        async def incomplete_shutdown():
            assert not execution.stop(timeout_seconds=0)
        monkeypatch.setattr(main, '_start_population_runtime_on_startup', startup)
        monkeypatch.setattr(main, '_stop_population_runtime_on_shutdown', incomplete_shutdown)
        monkeypatch.setattr(main, 'runtime_execution', execution)
        monkeypatch.setattr(main, 'health', lambda: {'status': 'ok'})
        queues = [Queue(maxsize=128) for _ in range(4)]
        queues[1].put(_encode(dict(schema=1, kind='shutdown', generation=None)))
        task = asyncio.create_task(_run_child(command_channel(queues[0]), *queues[1:], settings_json()))
        try:
            await asyncio.sleep(.1)
            messages = []
            while True:
                try:
                    messages.append(_decode(queues[2].get_nowait()))
                except Empty:
                    break
            assert not any(item['kind'] == 'stopped' for item in messages)
            assert not task.done()
        finally:
            release.set()
            await asyncio.wait_for(task, 2)
            await asyncio.to_thread(execution.stop)
        assert resource_closed.is_set()
        assert any(_decode(queues[2].get_nowait())['kind'] == 'stopped'
                   for _ in range(queues[2].qsize()))
    asyncio.run(run())


def test_parent_death_closes_child_even_when_result_queue_is_full(monkeypatch):
    from queue import Queue
    from app import main
    import app.services.runtime_process as module
    class Parent:
        alive = True
        def is_alive(self):
            return self.alive
    async def run():
        parent = Parent()
        stopped = asyncio.Event()
        async def startup():
            pass
        async def shutdown():
            stopped.set()
        monkeypatch.setattr(module.multiprocessing, 'parent_process', lambda: parent)
        monkeypatch.setattr(main, '_start_population_runtime_on_startup', startup)
        monkeypatch.setattr(main, '_stop_population_runtime_on_shutdown', shutdown)
        monkeypatch.setattr(main, 'runtime_execution', None)
        monkeypatch.setattr(main, 'health', lambda: {'status': 'ok'})
        queues = [Queue(maxsize=1) for _ in range(4)]
        task = asyncio.create_task(module._run_child(command_channel(queues[0]), *queues[1:], settings_json()))
        try:
            await asyncio.sleep(.05)
            assert queues[2].full()
            parent.alive = False
            done, _ = await asyncio.wait([task], timeout=.3)
            assert task in done
            assert stopped.is_set()
        finally:
            if not task.done():
                task.cancel()
                while not task.done():
                    if not queues[2].empty():
                        queues[2].get_nowait()
                    await asyncio.sleep(.02)
                await asyncio.gather(task, return_exceptions=True)
    asyncio.run(run())


def abandoned_result_child(commands, controls, results, notifications, settings):
    from time import monotonic
    from app import main
    import app.services.runtime_process as module
    deadline = monotonic() + .15
    class Parent:
        def is_alive(self):
            return monotonic() < deadline
    async def nothing():
        pass
    module.multiprocessing.parent_process = lambda: Parent()
    main._start_population_runtime_on_startup = nothing
    main._stop_population_runtime_on_shutdown = nothing
    main.runtime_execution = None
    main.health = lambda: {'status': 'ok', 'large': 'x' * (1024 * 1024)}
    module.runtime_child_main(commands, controls, results, notifications, settings)


def test_real_spawn_abandons_result_feeder_only_after_parent_death():
    import multiprocessing
    context = multiprocessing.get_context('spawn')
    queues = [context.Queue(maxsize=1) for _ in range(4)]
    process = context.Process(target=abandoned_result_child, args=(command_channel(queues[0]), *queues[1:], settings_json()))
    process.start()
    try:
        process.join(5)
        assert not process.is_alive(), '无人读的结果 pipe 不得阻塞孤立 child 退出'
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        for queue in queues:
            queue.cancel_join_thread()
            queue.close()


def parent_dies_after_stopped_child(commands, controls, results, notifications, settings):
    from app import main
    import app.services.runtime_process as module
    class Parent:
        alive = True
        def is_alive(self):
            return self.alive
    parent = Parent()
    original_put = results.put_nowait
    def put(value):
        original_put(value)
        if module._decode(value)['kind'] == 'stopped':
            parent.alive = False
    async def nothing():
        pass
    results.put_nowait = put
    module.multiprocessing.parent_process = lambda: parent
    main._start_population_runtime_on_startup = nothing
    main._stop_population_runtime_on_shutdown = nothing
    main.runtime_execution = None
    main.health = lambda: {'status': 'ok', 'large': 'x' * (1024 * 1024)}
    module.runtime_child_main(commands, controls, results, notifications, settings)


def test_real_spawn_monitors_parent_until_final_stopped_flush():
    import multiprocessing
    from app.services.runtime_process import _encode
    context = multiprocessing.get_context('spawn')
    queues = [context.Queue(maxsize=128) for _ in range(4)]
    queues[1].put(_encode(dict(schema=1, kind='shutdown', generation=None)))
    process = context.Process(target=parent_dies_after_stopped_child, args=(command_channel(queues[0]), *queues[1:], settings_json()))
    process.start()
    try:
        process.join(5)
        assert not process.is_alive(), 'STOPPED 入队后仍需监督 parent 与实际 flush'
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        for queue in queues:
            queue.cancel_join_thread()
            queue.close()


def credit_observing_child(command_channel, controls, results, notifications, settings):
    from app import main
    import app.services.runtime_process as module
    original_startup = main._start_population_runtime_on_startup
    original_health = main.health
    async def startup():
        await original_startup()
        assert main.runtime_execution._execution_credit is command_channel.execution_credit
    main._start_population_runtime_on_startup = startup
    main.health = lambda: dict(original_health(), shared_execution_credit=True)
    module.runtime_child_main(command_channel, controls, results, notifications, settings)


def test_real_spawn_installs_command_credit_into_original_owner(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', credit_observing_child)
    async def run():
        host = RuntimeProcess(settings_json())
        try:
            await asyncio.wait_for(host.start(), 20)
            assert host.snapshot()['shared_execution_credit'] is True
        finally:
            await host.close()
    asyncio.run(run())
