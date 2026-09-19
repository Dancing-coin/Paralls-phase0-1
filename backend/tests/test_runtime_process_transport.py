"""真实 child 的原 WS 业务体与 parent 实际发送回执。"""
import asyncio
import pytest

from app.services.runtime_process import RuntimeProcess
from test_runtime_process import settings_json


def test_real_spawn_ws_reuses_original_business_and_waits_for_socket_receipt():
    async def run():
        host = RuntimeProcess(settings_json())
        messages = []
        entered, release = asyncio.Event(), asyncio.Event()
        async def send(message):
            entered.set()
            await release.wait()
            messages.append(message)
        async def close(code, reason):
            pass
        try:
            await host.start()
            await host.connect('connection:test', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await host.envelope('connection:test', {'message_type': 'character_actor_status',
                                                   'payload': {'actor_id': 'char_b'}})
            await asyncio.wait_for(entered.wait(), 3)
            assert host.snapshot()['pending_send'] == 1
            assert messages == []
            release.set()
            for _ in range(100):
                if messages and host.snapshot()['pending_send'] == 0:
                    break
                await asyncio.sleep(.02)
            assert messages
            assert messages[0]['message_type'] in {'ack', 'character_actor_status'}
            assert host.snapshot()['pending_send'] == 0
            await host.disconnect('connection:test')
        finally:
            release.set()
            await host.close()
    asyncio.run(run())


def test_disconnect_control_cancels_actual_parent_send_and_closes_original_child_session():
    async def run():
        host = RuntimeProcess(settings_json())
        entered, cancelled = asyncio.Event(), asyncio.Event()
        async def send(message):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        async def close(code, reason):
            pass
        try:
            await host.start()
            await host.connect('connection:blocked', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await host.envelope('connection:blocked', {'message_type': 'character_actor_status',
                                                      'payload': {'actor_id': 'char_b'}})
            await asyncio.wait_for(entered.wait(), 3)
            await asyncio.wait_for(host.disconnect('connection:blocked'), 3)
            assert cancelled.is_set()
            assert host.snapshot()['pending_send'] == 0
        finally:
            await host.close()
    asyncio.run(run())


def test_disconnect_before_parent_delivery_starts_releases_notification():
    async def run():
        host = RuntimeProcess(settings_json())
        scheduled = asyncio.Event()
        async def delayed(value):
            scheduled.set()
            await asyncio.Event().wait()
        host._deliver = delayed
        async def send(message):
            raise AssertionError('已经断连，不应发送')
        async def close(code, reason):
            pass
        try:
            await host.start()
            await host.connect('connection:queued', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await host.envelope('connection:queued', {'message_type': 'character_actor_status',
                                                     'payload': {'actor_id': 'char_b'}})
            await asyncio.wait_for(scheduled.wait(), 3)
            await asyncio.wait_for(host.disconnect('connection:queued'), 3)
            assert host.snapshot()['pending_send'] == 0
        finally:
            await host.close()
    asyncio.run(run())


def http_owner_asserting_child(commands, controls, results, notifications, settings):
    from threading import current_thread
    from app import main
    from app.services.runtime_process import runtime_child_main
    startup = main._start_population_runtime_on_startup
    async def checked_startup():
        await startup()
        original = main.interaction_orchestration_service.execute
        original_read = main.siming_audit_writer.latest_read_model
        def checked(payload):
            assert current_thread() is main.runtime_execution._thread
            return original(payload)
        def checked_read(**kwargs):
            assert current_thread() is main.runtime_execution._thread
            return original_read(**kwargs)
        main.interaction_orchestration_service.execute = checked
        main.siming_audit_writer.latest_read_model = checked_read
    main._start_population_runtime_on_startup = checked_startup
    runtime_child_main(commands, controls, results, notifications, settings)


def test_real_spawn_http_preserves_typed_routes_and_original_owner(monkeypatch):
    import json
    import pytest
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', http_owner_asserting_child)
    async def run():
        host = RuntimeProcess(settings_json())
        async def request(name, path, method, body):
            return await host.request('http.request', dict(route=name, path=path, method=method,
                query='', headers=[['content-type', 'application/json']], remote_host='127.0.0.1',
                remote_port=1, body=json.dumps(body)))
        try:
            await host.start()
            response = await request('orchestrate_structured_interaction', '/interaction/orchestrate', 'POST',
                {'intent': {'intent_id': 'intent:inspect', 'actor_id': 'char_a',
                            'target_refs': {'object_ids': ['obj_box']}, 'semantic_intent': 'inspect'},
                 'player_id': 'player', 'target_object_id': 'obj_box', 'producer_ts': 1})
            assert response['status'] == 200
            assert json.loads(response['body'])['plan']['policy'] == 'semantic-only'
            rejected = await request('orchestrate_structured_interaction', '/interaction/orchestrate', 'POST',
                {'intent': {'intent_id': 'intent:bad', 'actor_id': 'char_a', 'semantic_intent': 'inspect'},
                 'raw_keyboard': {'space': True}})
            assert rejected['status'] == 422
            read = await request('debug_siming_read_model', '/debug/siming/read-model/room-test', 'GET', {})
            assert read['status'] == 200
            with pytest.raises(module.RuntimeProcessError, match='http_route'):
                await request('debug_panel', '/debug/panel', 'GET', {})
            with pytest.raises(module.RuntimeProcessError, match='http_route'):
                await request('orchestrate_structured_interaction', '/debug/panel', 'POST', {})
        finally:
            await host.close()
    asyncio.run(run())


def test_cancelled_connect_cleans_child_session_before_reusing_reference():
    async def run():
        host = RuntimeProcess(settings_json())
        child_connected = asyncio.Event()
        original = host.request
        async def held(operation, payload):
            result = await original(operation, payload)
            if operation == 'transport.connect':
                child_connected.set()
                await asyncio.Event().wait()
            return result
        host.request = held
        async def send(message):
            pass
        async def close(code, reason):
            pass
        try:
            await host.start()
            connecting = asyncio.create_task(host.connect('connection:cancel', path='/ws', query={},
                remote_host='127.0.0.1', send_json=send, close_socket=close))
            await asyncio.wait_for(child_connected.wait(), 3)
            connecting.cancel()
            await asyncio.gather(connecting, return_exceptions=True)
            await asyncio.wait_for(host.disconnect('connection:cancel'), 3)
            host.request = original
            await host.connect('connection:cancel', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await host.disconnect('connection:cancel')
        finally:
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def test_child_death_cancels_pending_socket_output_without_sending_late():
    async def run():
        host = RuntimeProcess(settings_json())
        entered, release, closed = asyncio.Event(), asyncio.Event(), asyncio.Event()
        sent = []
        async def send(message):
            entered.set()
            await release.wait()
            sent.append(message)
        async def close(code, reason):
            closed.set()
        try:
            await host.start()
            await host.connect('connection:death', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await host.envelope('connection:death', {'message_type': 'character_actor_status',
                                                    'payload': {'actor_id': 'char_b'}})
            await asyncio.wait_for(entered.wait(), 3)
            host.process.terminate()
            await asyncio.to_thread(host.process.join, 3)
            await asyncio.wait_for(closed.wait(), .5)
            release.set()
            for _ in range(20):
                if host.snapshot()['pending_send'] == 0:
                    break
                await asyncio.sleep(.02)
            assert sent == []
            assert host.snapshot()['pending_send'] == 0
        finally:
            release.set()
            await host.close()
    asyncio.run(run())


def cancel_unstarted_session_child(commands, controls, results, notifications, settings):
    import app.services.runtime_process as module
    original = module.asyncio.create_task
    def create(coroutine, **kwargs):
        task = original(coroutine, **kwargs)
        if coroutine.cr_code.co_name == 'serve':
            task.cancel()
        return task
    module.asyncio.create_task = create
    module.runtime_child_main(commands, controls, results, notifications, settings)


def test_unstarted_child_session_cancellation_has_terminal_receipt(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', cancel_unstarted_session_child)
    async def run():
        host = RuntimeProcess(settings_json())
        async def send(message):
            pass
        async def close(code, reason):
            pass
        try:
            await host.start()
            await host.connect('connection:notstarted', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await asyncio.wait_for(host.disconnect('connection:notstarted'), .5)
        finally:
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def delayed_command_child(commands, controls, results, notifications, settings):
    from time import sleep
    import app.services.runtime_process as module
    original = commands.queue.get
    first = True
    def get(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            sleep(.3)
        return original(*args, **kwargs)
    commands.queue.get = get
    module.runtime_child_main(commands, controls, results, notifications, settings)


def test_disconnect_before_connect_command_is_consumed_does_not_create_late_session(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', delayed_command_child)
    async def run():
        host = RuntimeProcess(settings_json())
        async def send(message):
            pass
        async def close(code, reason):
            pass
        try:
            await host.start()
            connecting = asyncio.create_task(host.connect('connection:earlycancel', path='/ws', query={},
                remote_host='127.0.0.1', send_json=send, close_socket=close))
            while host.pending_count == 0:
                await asyncio.sleep(0)
            connecting.cancel()
            await asyncio.gather(connecting, return_exceptions=True)
            await asyncio.wait_for(host.disconnect('connection:earlycancel'), 3)
            while host.pending_count:
                await asyncio.sleep(.02)
            await host.connect('connection:earlycancel', path='/ws', query={}, remote_host='127.0.0.1',
                               send_json=send, close_socket=close)
            await host.disconnect('connection:earlycancel')
        finally:
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def test_original_ws_cleanup_finishes_inside_cancelled_asgi_scope():
    from types import SimpleNamespace
    from anyio import CancelScope
    from fastapi import WebSocketDisconnect
    from app import main
    async def run():
        returned = False
        class Socket:
            query_params = {}
            client = SimpleNamespace(host='127.0.0.1')
            async def accept(self):
                pass
            async def send_json(self, message):
                pass
            async def close(self, **kwargs):
                pass
            async def receive_json(self):
                scope.cancel()
                raise WebSocketDisconnect()
        await main._start_population_runtime_on_startup()
        try:
            with CancelScope() as scope:
                await main.websocket_endpoint(Socket())
                returned = True
            assert returned, 'ASGI外层取消不能中断原连接finally收口'
            assert not main._cognition_output_routes.connections
        finally:
            await main._stop_population_runtime_on_shutdown()
    asyncio.run(run())


def test_child_failure_releases_terminal_waiting_on_full_control():
    from queue import Queue
    from types import SimpleNamespace
    async def run():
        host = RuntimeProcess(settings_json())
        original = host._controls
        host._controls = Queue(maxsize=1)
        host._controls.put('full')
        host.process = SimpleNamespace(is_alive=lambda: True)
        result = asyncio.get_running_loop().create_future()
        result.set_result('sent')
        value = dict(delivery_id='delivery', connection_ref='connection')
        terminal = asyncio.create_task(host._finish_delivery(value, result))
        host._send_tasks['delivery'] = ('connection', terminal)
        host._finalizing_sends.add('delivery')
        try:
            await asyncio.sleep(.03)
            assert not terminal.done()
            host._fail('runtime_child_exited')
            done, _ = await asyncio.wait([terminal], timeout=.15)
            assert terminal in done, 'child 失联必须唤醒已进入满 control 的终态等待'
            assert not host._send_tasks
        finally:
            terminal.cancel()
            await asyncio.gather(terminal, return_exceptions=True)
            for queue in (host._commands, original, host._results, host._notifications):
                queue.close()
                queue.join_thread()
    asyncio.run(run())


def test_child_shutdown_stops_reader_before_closing_sessions(monkeypatch):
    from queue import Queue
    from app import main
    import app.services.runtime_process as module
    from test_runtime_process import command_channel
    async def run():
        entered, cancelling, release_cleanup, late_started, release_late = (asyncio.Event() for _ in range(5))
        queues = [Queue(maxsize=128) for _ in range(4)]
        original_get = module._get
        reads = 0
        async def controlled_get(queue):
            nonlocal reads
            if queue is queues[0]:
                reads += 1
                if reads == 2:
                    await cancelling.wait()
            return await original_get(queue)
        async def startup(): pass
        async def shutdown(): pass
        async def endpoint(channel):
            if channel.connection_ref == 'first':
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelling.set()
                    await release_cleanup.wait()
            else:
                late_started.set()
                await release_late.wait()
        from types import SimpleNamespace
        monkeypatch.setattr(module, 'uuid4', lambda: SimpleNamespace(hex='generation'))
        monkeypatch.setattr(module, '_get', controlled_get)
        monkeypatch.setattr(main, '_start_population_runtime_on_startup', startup)
        monkeypatch.setattr(main, '_stop_population_runtime_on_shutdown', shutdown)
        monkeypatch.setattr(main, 'runtime_execution', None)
        monkeypatch.setattr(main, 'websocket_endpoint', endpoint)
        monkeypatch.setattr(main, 'health', lambda: {'status': 'ok'})
        for number, ref in enumerate(('first', 'late'), 1):
            queues[0].put(module._encode(dict(schema=1, kind='command', generation='generation', sequence=number,
                operation='transport.connect', payload=dict(connection_ref=ref, connection_generation=ref,
                    path='/ws', query={}, remote_host='127.0.0.1'))))
        task = asyncio.create_task(module._run_child(command_channel(queues[0]), *queues[1:], settings_json()))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            queues[1].put(module._encode(dict(schema=1, kind='shutdown', generation='generation')))
            await asyncio.wait_for(cancelling.wait(), 1)
            await asyncio.sleep(.05)
            assert not late_started.is_set(), '关闭现有 session 时 reader 不得创建新 session'
            release_cleanup.set()
            await asyncio.wait_for(asyncio.shield(task), 1)
        finally:
            release_cleanup.set()
            release_late.set()
            await asyncio.wait_for(task, 2)
    asyncio.run(run())


def binding_fence_child(commands, controls, results, notifications, settings):
    from time import time
    from app import main
    from app.services.runtime_process import runtime_child_main
    async def endpoint(channel):
        await channel.accept()
        await channel.synchronize_binding(['session:test', 1, int(time()) + 60])
        first = asyncio.create_task(channel.send_json({'message_type': 'old_output', 'payload': {}}))
        await channel.receive_json()
        await channel.synchronize_binding(['session:test', 2, int(time()) + 60])
        await asyncio.gather(first, return_exceptions=True)
        await channel.send_json({'message_type': 'new_output', 'payload': {}})
        await channel.synchronize_binding(['session:test', 2, int(time()) - 1])
        try:
            await channel.send_json({'message_type': 'expired_output', 'payload': {}})
        except Exception:
            pass
        await channel.close()
    main.websocket_endpoint = endpoint
    runtime_child_main(commands, controls, results, notifications, settings)


def test_real_spawn_parent_rechecks_binding_revision_and_lease(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', binding_fence_child)
    async def run():
        host = RuntimeProcess(settings_json())
        entered, closed, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
        messages = []
        async def send(message):
            if message['message_type'] == 'old_output':
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
            messages.append(message['message_type'])
        async def close(code, reason):
            closed.set()
        try:
            await host.start()
            await host.connect('binding:test', path='/ws', query={}, remote_host='127.0.0.1', send_json=send, close_socket=close)
            await asyncio.wait_for(entered.wait(), 2)
            await host.envelope('binding:test', {'message_type': 'advance', 'payload': {}})
            await asyncio.wait_for(closed.wait(), 2)
            assert cancelled.is_set()
            assert messages == ['new_output']
        finally:
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def original_binding_child(commands, controls, results, notifications, settings):
    from time import time
    from app import main
    from app.services.runtime_process import runtime_child_main
    original_endpoint = main.websocket_endpoint
    async def endpoint(channel):
        now = int(time())
        credential = await asyncio.wrap_future(main.runtime_execution.submit(lambda:
            main.websocket_session_auth_service.create_trusted_local_launch_credential(principal_ref='player',
                allowed_actor_refs=('character:char_a',), issued_at=now, expires_at=now+60)))
        channel.inbound.put_nowait(dict(message_type='websocket_session_bind', payload=dict(
            credential_kind='trusted_local_launch', credential=credential, protocol_version=1)))
        original_receive = channel.receive_json
        async def receive():
            value = await original_receive()
            if value.get('message_type') == 'revoke_control':
                pin = main._get_dialogue_coordinator()._connections[channel.connection_ref]
                await asyncio.wrap_future(main.runtime_execution.submit(lambda:
                    main._revoke_websocket_session_for_transport(session_ref=pin[0], connection_ref=channel.connection_ref,
                        reason_code='controlled_revoke', now=int(time()))))
            return value
        channel.receive_json = receive
        await original_endpoint(channel)
    main.websocket_endpoint = endpoint
    runtime_child_main(commands, controls, results, notifications, settings)


def test_original_main_binding_and_revocation_reach_parent_fence(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', original_binding_child)
    async def run():
        host = RuntimeProcess(settings_json())
        bound, revoked = asyncio.Event(), asyncio.Event()
        async def send(message):
            state = host._connections['original:test']
            if message['message_type'] == 'websocket_session_bound':
                assert len(state['binding_pin']) == 3 and state['state_revision'] == 1
                bound.set()
            if message['message_type'] == 'websocket_session_revoked':
                assert state['revoked'] is True and state['state_revision'] == 2
                revoked.set()
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('original:test', path='/ws', query={}, remote_host='127.0.0.1', send_json=send, close_socket=close)
            await asyncio.wait_for(bound.wait(), 2)
            await host.envelope('original:test', dict(message_type='revoke_control', payload={}))
            await asyncio.wait_for(revoked.wait(), 2)
            await host.disconnect('original:test')
        finally:
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def test_parent_blocked_send_is_cancelled_at_original_lease_deadline(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'time', lambda: 100.95)
    async def run():
        host = RuntimeProcess(settings_json())
        cancelled = asyncio.Event()
        async def send(message):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        host._connections['lease'] = dict(closed=False, generation='epoch', state_revision=1, send_lock=asyncio.Lock(),
            binding_pin=['session', 1, 100], revoked=False, send=send)
        try:
            result = await asyncio.wait_for(host._deliver(dict(delivery_id='delivery', connection_ref='lease',
                connection_generation='epoch', state_revision=1, message=dict(message_type='output'))), .3)
            assert result == 'failed' and cancelled.is_set()
        finally:
            for queue in (host._commands, host._controls, host._results, host._notifications):
                queue.close()
                queue.join_thread()
    asyncio.run(run())



async def wait_queued_child_blocked(release):
    from pathlib import Path
    async with asyncio.timeout(3):
        while not Path(str(release) + '.blocked').exists():
            await asyncio.sleep(.005)

def queued_runtime_child(commands, controls, results, notifications, settings):
    from time import time, sleep
    from pathlib import Path
    from app import main
    from app.services.runtime_process import runtime_child_main
    async def endpoint(channel):
        async def enqueue(request, *, transferred=False, expected_pin=None, request_sequence=None):
            assert transferred and expected_pin == ['session:test', 1, lease]
            future = main.runtime_execution.submit_admitted(lambda: request.command.payload['actor_id'])
            async def finish():
                actor = await asyncio.wrap_future(future)
                await channel.send_json(dict(message_type='runtime_completion', payload=dict(
                    request_id=request.request_id, status='owner_finished', messages=[dict(message_type='ack',
                        payload=dict(accepted=True, source_type='character_actor_status', actor_id=actor))])), request_sequence=request_sequence)
                await channel.finish_runtime_request(request.request_id, request_sequence)
            task = asyncio.create_task(finish())
            running.add(task)
            task.add_done_callback(running.discard)
        running = set()
        channel.runtime_enqueue = enqueue
        lease = int(time()) + 60
        await channel.synchronize_binding(['session:test', 1, lease])
        await channel.send_json(dict(message_type='ready_for_commands', payload={}))
        # 模拟 child loop 在不可分割工作中暂不消费 IPC，parent 仍须真正入队。
        Path(channel.query_params['release_file'] + '.blocked').touch()
        while not Path(channel.query_params['release_file']).exists():
            sleep(.01)
        try:
            await channel.receive_json()
        finally:
            for task in running: task.cancel()
            await asyncio.gather(*running, return_exceptions=True)
    main.websocket_endpoint = endpoint
    runtime_child_main(commands, controls, results, notifications, settings)


def test_parent_accepts_concrete_runtime_command_while_child_loop_is_busy(monkeypatch, tmp_path):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', queued_runtime_child)
    async def run():
        host = RuntimeProcess(settings_json())
        ready, completed = asyncio.Event(), asyncio.Event()
        messages = []
        async def send(message):
            messages.append(message)
            if message['message_type'] == 'ready_for_commands': ready.set()
            if message['message_type'] == 'runtime_completion': completed.set()
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('enqueue:test', path='/ws', query={'release_file': str(tmp_path/'release')}, remote_host='127.0.0.1', send_json=send, close_socket=close)
            await asyncio.wait_for(ready.wait(), 2)
            await wait_queued_child_blocked(tmp_path / 'release')
            result = await host.enqueue_runtime('enqueue:test', dict(request_id='request:1', command=dict(
                message_type='character_actor_status', payload=dict(actor_id='char_a'))))
            assert result['accepted'] is True
            assert not completed.is_set()
            assert host.snapshot()['execution_credit']['current'] >= 1
            (tmp_path/'release').touch()
            await asyncio.wait_for(completed.wait(), 2)
            kinds = [row['message_type'] for row in messages]
            assert kinds.index('runtime_admission') < kinds.index('runtime_completion')
            await host.disconnect('enqueue:test')
            assert host.snapshot()['execution_credit']['current'] == 0
        finally:
            (tmp_path/'release').touch()
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def test_binding_publishers_preserve_revision_order_when_results_are_full():
    from queue import Queue
    import app.services.runtime_process as module
    async def run():
        results, notifications = Queue(128), Queue(128)
        for _ in range(128): results.put('occupied')
        first_waiting = asyncio.Event()
        deliveries = {}
        async def emit(kind, **payload):
            if payload['state_revision'] == 1: first_waiting.set()
            await module._put(results, dict(schema=1, kind=kind, **payload))
        channel = module._RuntimeConnection(dict(connection_ref='connection', connection_generation='epoch',
            query={}, remote_host='127.0.0.1'), 'process', notifications, emit, deliveries, asyncio.Event())
        first = channel.synchronize_binding(['session', 1, 1000])
        await first_waiting.wait()
        results.get_nowait()
        second = channel.synchronize_binding(['session', 1, 1000], revoked=True)
        await asyncio.sleep(.005)
        revisions = []
        try:
            async with asyncio.timeout(1):
                while not first.done() or not second.done():
                    while not results.empty():
                        raw = results.get_nowait()
                        if raw != 'occupied':
                            row = module._decode(raw)
                            revisions.append(row['state_revision'])
                            deliveries[row['delivery_id']].set_result('sent')
                    await asyncio.sleep(.005)
            await asyncio.gather(first, second)
            assert revisions == [1, 2]
        finally:
            first.cancel(); second.cancel()
            await asyncio.gather(first, second, return_exceptions=True)
    asyncio.run(run())


def test_parent_drops_mirror_frame_at_exact_original_lease(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'time', lambda: 100.5)
    async def run():
        host = RuntimeProcess(settings_json())
        sent = []
        async def send(message): sent.append(message)
        host._connections['lease'] = dict(closed=False, generation='epoch', state_revision=1, send_lock=asyncio.Lock(),
            binding_pin=['session', 1, 100], revoked=False, send=send)
        try:
            result = await host._deliver(dict(delivery_id='delivery', connection_ref='lease',
                connection_generation='epoch', state_revision=1, lease_deadline=100, message=dict(message_type='gameplay_mirror_delivery')))
            assert result == 'failed' and not sent
        finally:
            for queue in (host._commands, host._controls, host._results, host._notifications):
                queue.close(); queue.join_thread()
    asyncio.run(run())


def test_parent_preserves_original_inclusive_cognition_lease(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'time', lambda: 100.5)
    async def run():
        host = RuntimeProcess(settings_json())
        sent = []
        async def send(message): sent.append(message)
        host._connections['lease'] = dict(closed=False, generation='epoch', state_revision=1, send_lock=asyncio.Lock(),
            binding_pin=['session', 1, 100], revoked=False, send=send)
        try:
            result = await host._deliver(dict(delivery_id='delivery', connection_ref='lease',
                connection_generation='epoch', state_revision=1, message=dict(message_type='character_agent_execution')))
            assert result == 'sent' and len(sent) == 1
        finally:
            for queue in (host._commands, host._controls, host._results, host._notifications):
                queue.close(); queue.join_thread()
    asyncio.run(run())


def test_shutdown_releases_accepted_commands_still_in_ipc(monkeypatch, tmp_path):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', queued_runtime_child)
    async def run():
        host = RuntimeProcess(settings_json())
        ready = asyncio.Event()
        async def send(message):
            if message['message_type'] == 'ready_for_commands': ready.set()
        async def close(code, reason): pass
        await host.start()
        await host.connect('shutdown:test', path='/ws', query={'release_file': str(tmp_path/'release')}, remote_host='127.0.0.1', send_json=send, close_socket=close)
        try:
            await asyncio.wait_for(ready.wait(), 2)
            await wait_queued_child_blocked(tmp_path / 'release')
            for index in range(5):
                row = await host.enqueue_runtime('shutdown:test', dict(request_id=str(index), command=dict(
                    message_type='character_actor_status', payload=dict(actor_id='char_a'))))
                assert row['accepted']
            assert host.snapshot()['execution_credit']['current'] >= 5
            closing = asyncio.create_task(host.close())
            await asyncio.sleep(.02)
            (tmp_path/'release').touch()
            await closing
        finally:
            (tmp_path/'release').touch()
            await host.close()
        assert host.process.exitcode == 0
        assert host.snapshot()['execution_credit']['current'] == 0
        assert host.snapshot()['runtime_pending'] == 0
    asyncio.run(run())


def test_real_spawn_enqueue_reuses_original_main_owner_commands(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', original_binding_child)
    async def run():
        host = RuntimeProcess(settings_json())
        bound, completed = asyncio.Event(), asyncio.Event()
        results = []
        async def send(message):
            if message['message_type'] == 'websocket_session_bound': bound.set()
            if message['message_type'] == 'runtime_completion':
                results.append(message['payload'])
                if len(results) == 5: completed.set()
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('main:enqueue', path='/ws', query={}, remote_host='127.0.0.1', send_json=send, close_socket=close)
            await asyncio.wait_for(bound.wait(), 2)
            for index in range(5):
                result = await host.enqueue_runtime('main:enqueue', dict(request_id=str(index), command=dict(
                    message_type='character_actor_status', payload=dict(actor_id='char_a'))))
                assert result['accepted']
            await asyncio.wait_for(completed.wait(), 3)
            assert [row['request_id'] for row in results] == list(map(str, range(5)))
            assert all(any(message['message_type'] == 'ack' and message['payload'].get('accepted') is True
                for message in row['messages']) for row in results)
            async with asyncio.timeout(2):
                while host.snapshot()['runtime_pending']:
                    await asyncio.sleep(.02)
            assert (await host.enqueue_runtime('main:enqueue', dict(request_id='0', command=dict(
                message_type='character_actor_status', payload=dict(actor_id='char_a')))))['accepted']
            async with asyncio.timeout(2):
                while len(results) < 6 or host.snapshot()['runtime_pending']:
                    await asyncio.sleep(.02)
            assert results[-1]['request_id'] == '0'
            await host.disconnect('main:enqueue')
        finally:
            await host.close()
        assert host.process.exitcode == 0
        assert host.snapshot()['execution_credit']['current'] == 0
    asyncio.run(run())


def test_parent_enqueue_shares_capacity_and_rejects_duplicate_or_invalid_input(monkeypatch, tmp_path):
    import pytest
    from pydantic import ValidationError
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', queued_runtime_child)
    async def run():
        host = RuntimeProcess(settings_json())
        ready = asyncio.Event()
        async def send(message):
            if message['message_type'] == 'ready_for_commands': ready.set()
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('capacity:test', path='/ws', query={'release_file': str(tmp_path/'release')},
                remote_host='127.0.0.1', send_json=send, close_socket=close)
            await asyncio.wait_for(ready.wait(), 2)
            await wait_queued_child_blocked(tmp_path / 'release')
            rows = []
            for index in range(130):
                rows.append(await host.enqueue_runtime('capacity:test', dict(request_id=str(index), command=dict(
                    message_type='character_actor_status', payload=dict(actor_id='char_a')))))
            assert 1 <= sum(row['accepted'] for row in rows) <= 128
            assert any(not row['accepted'] for row in rows)
            duplicate = await host.enqueue_runtime('capacity:test', dict(request_id='0', command=dict(
                message_type='character_actor_status', payload=dict(actor_id='char_a'))))
            assert duplicate == dict(request_id='0', accepted=False, reason='duplicate_pending_request')
            sequence = host._sequence
            with pytest.raises(ValidationError):
                await host.enqueue_runtime('capacity:test', dict(request_id='nested', command=dict(message_type='runtime_enqueue', payload={})))
            assert host._sequence == sequence
            counters = host.snapshot()['execution_credit']
            assert 0 <= counters['current'] <= 128
            # 正常跨进程争用也可能使观测失效；容量权威始终是原 semaphore。
            assert counters['peak'] is None or counters['peak'] <= 128
        finally:
            (tmp_path/'release').touch()
            await host.close()
        assert host.process.exitcode == 0
        assert host.snapshot()['execution_credit']['current'] == 0
    asyncio.run(run())


def blocked_owner_original_child(commands, controls, results, notifications, settings):
    from pathlib import Path
    from time import sleep
    from app import main
    original_endpoint = main.websocket_endpoint
    original_handle = main._dialogue_connection_envelope
    async def endpoint(channel):
        directory = Path(channel.query_params['control_dir'])
        def execute(command, context):
            if 'character_actor_status' in command:
                with (directory/'executed').open('a') as file: file.write('executed\n')
            return original_handle(command, context)
        main._dialogue_connection_envelope = execute
        async def block_after_bind():
            while not (directory/'block').exists(): await asyncio.sleep(.02)
            def block():
                (directory/'entered').touch()
                while not (directory/'release').exists(): sleep(.01)
            main.runtime_execution.submit(block)
        task = asyncio.create_task(block_after_bind())
        try:
            await original_endpoint(channel)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    main.websocket_endpoint = endpoint
    original_binding_child(commands, controls, results, notifications, settings)


def test_real_spawn_disconnect_cancels_accepted_owner_commands_before_execution(monkeypatch, tmp_path):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', blocked_owner_original_child)
    async def run():
        host = RuntimeProcess(settings_json())
        bound = asyncio.Event()
        completions = []
        async def send(message):
            if message['message_type'] == 'websocket_session_bound': bound.set()
            if message['message_type'] == 'runtime_completion': completions.append(message)
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('cancel:enqueue', path='/ws', query={'control_dir': str(tmp_path)}, remote_host='127.0.0.1',
                send_json=send, close_socket=close)
            await asyncio.wait_for(bound.wait(), 2)
            (tmp_path/'block').touch()
            async with asyncio.timeout(2):
                while not (tmp_path/'entered').exists(): await asyncio.sleep(.02)
            for index in range(5):
                result = await host.enqueue_runtime('cancel:enqueue', dict(request_id=str(index), command=dict(
                    message_type='character_actor_status', payload=dict(actor_id='char_a'))))
                assert result['accepted']
            disconnect = asyncio.create_task(host.disconnect('cancel:enqueue'))
            await asyncio.sleep(.1)
            (tmp_path/'release').touch()
            await asyncio.wait_for(disconnect, 2)
            assert not (tmp_path/'executed').exists()
            assert not completions
        finally:
            (tmp_path/'release').touch()
            await host.close()
        assert host.process.exitcode == 0
        assert host.snapshot()['execution_credit']['current'] == 0
    asyncio.run(run())


def test_runtime_enqueue_waits_for_prior_original_envelope_barrier(monkeypatch, tmp_path):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', blocked_owner_original_child)
    async def run():
        host = RuntimeProcess(settings_json())
        bound, completed = asyncio.Event(), asyncio.Event()
        async def send(message):
            if message['message_type'] == 'websocket_session_bound': bound.set()
            if message['message_type'] == 'runtime_completion': completed.set()
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('barrier:test', path='/ws', query={'control_dir': str(tmp_path)}, remote_host='127.0.0.1',
                send_json=send, close_socket=close)
            await asyncio.wait_for(bound.wait(), 2)
            (tmp_path/'block').touch()
            async with asyncio.timeout(2):
                while not (tmp_path/'entered').exists(): await asyncio.sleep(.02)
            await host.envelope('barrier:test', dict(message_type='character_actor_status', payload=dict(actor_id='char_a')))
            sequence = host._sequence
            admission = asyncio.create_task(host.enqueue_runtime('barrier:test', dict(request_id='after', command=dict(
                message_type='character_actor_status', payload=dict(actor_id='char_a')))))
            await asyncio.sleep(.05)
            assert not admission.done() and host._sequence == sequence
            (tmp_path/'release').touch()
            assert (await asyncio.wait_for(admission, 2))['accepted']
            await asyncio.wait_for(completed.wait(), 2)
            assert (tmp_path/'executed').read_text().splitlines() == ['executed', 'executed']
            await host.disconnect('barrier:test')
        finally:
            (tmp_path/'release').touch()
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


@pytest.mark.parametrize('generation,sequence', [('old', 2), ('new', 1)])
def test_old_generation_completion_cannot_remove_reconnected_pending(generation, sequence):
    async def run():
        host = RuntimeProcess(settings_json())
        acknowledged = asyncio.Event(); acknowledged.set()
        pending = dict(acknowledged=acknowledged, state_revision=1, connection_generation='new', request_sequence=2)
        host._runtime_pending[('same', 'request')] = pending
        async def send(message): raise AssertionError('旧输出不得发送')
        host._connections['same'] = dict(closed=False, generation='new', state_revision=1,
            send_lock=asyncio.Lock(), binding_pin=[], revoked=False, send=send)
        try:
            assert await host._deliver(dict(delivery_id='old', connection_ref='same',
                connection_generation=generation, request_sequence=sequence, state_revision=1, message=dict(message_type='runtime_completion',
                payload=dict(request_id='request')))) == 'failed'
            assert host._runtime_pending[('same', 'request')] is pending
        finally:
            for queue in (host._commands, host._controls, host._results, host._notifications):
                queue.close(); queue.join_thread()
    asyncio.run(run())


def test_full_parent_sends_backpressure_valid_notification_without_host_failure():
    from queue import Queue
    from types import SimpleNamespace
    import app.services.runtime_process as module
    async def run():
        host = RuntimeProcess(settings_json())
        real_queues = (host._commands, host._controls, host._results, host._notifications)
        host._notifications = Queue(128)
        host.process = SimpleNamespace(is_alive=lambda: False)
        host._generation = 'process'
        blocked = asyncio.Event()
        original = [asyncio.create_task(blocked.wait()) for _ in range(128)]
        host._send_tasks.update({str(i): ('connection', task) for i, task in enumerate(original)})
        host._notifications.put(module._encode(dict(schema=1, kind='send', generation='process',
            delivery_id='child', connection_ref='absent', connection_generation='old', message={})))
        reader = asyncio.create_task(host._read_notifications())
        try:
            await asyncio.sleep(.05)
            assert host._failure is None and not reader.done() and len(host._send_tasks) == 128
            host._send_tasks.pop('0')
            await asyncio.sleep(.05)
            assert host._failure is None and not reader.done() and 'child' not in host._send_tasks
        finally:
            reader.cancel(); blocked.set()
            await asyncio.gather(reader, *original, return_exceptions=True)
            for queue in real_queues:
                queue.close(); queue.join_thread()
    asyncio.run(run())


def expired_completion_child(*args):
    from time import time as wall_time
    import app.main as main
    import app.services.dialogue_continuation as dialogue
    original = main._dialogue_connection_envelope
    def execute(command, context):
        result = original(command, context)
        if 'character_actor_status' in command:
            # 原事实完成之后、原完成泵授权之前，控制时钟跨过已冻结租期。
            expired = wall_time() + 120
            main.time = dialogue.time = lambda: expired
        return result
    main._dialogue_connection_envelope = execute
    original_binding_child(*args)


def test_expired_original_completion_retires_parent_pending_without_sending(monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', expired_completion_child)
    async def run():
        host = RuntimeProcess(settings_json())
        messages = []
        async def send(message): messages.append(message)
        async def close(code, reason): pass
        try:
            await host.start()
            await host.connect('expired', path='/ws', query={}, remote_host='127.0.0.1', send_json=send, close_socket=close)
            async with asyncio.timeout(3):
                while not host._connections['expired']['binding_pin']:
                    await asyncio.sleep(.02)
            assert (await host.enqueue_runtime('expired', dict(request_id='expired-request', command=dict(
                message_type='character_actor_status', payload=dict(actor_id='char_a')))))['accepted']
            async with asyncio.timeout(2):
                while host.snapshot()['runtime_pending']:
                    await asyncio.sleep(.02)
            assert not any(row['message_type'] == 'runtime_completion' for row in messages)
            assert not host._connections['expired']['closed']
        finally:
            await host.close()
        assert host.process.exitcode == 0
    asyncio.run(run())


def test_old_terminal_cannot_retire_reused_request_and_terminal_waits_for_ack():
    from queue import Queue
    import app.services.runtime_process as module
    async def run():
        host = RuntimeProcess(settings_json())
        real_queues = (host._commands, host._controls, host._results, host._notifications)
        host._results = Queue(128)
        host._generation = 'process'
        pending = dict(acknowledged=asyncio.Event(), state_revision=1, connection_generation='connection',
            request_sequence=2, terminal=False)
        host._runtime_pending[('ref', 'reused')] = pending
        reader = asyncio.create_task(host._read_results())
        def emit(sequence):
            host._results.put(module._encode(dict(schema=1, kind='runtime_terminal', generation='process',
                connection_ref='ref', connection_generation='connection', request_id='reused', request_sequence=sequence)))
        try:
            emit(1)
            await asyncio.sleep(.03)
            assert host._runtime_pending[('ref', 'reused')] is pending and not pending['terminal']
            emit(2)
            await asyncio.sleep(.03)
            assert host._runtime_pending[('ref', 'reused')] is pending and pending['terminal']
            pending['acknowledged'].set()
            emit(2)
            await asyncio.sleep(.03)
            assert not host._runtime_pending and host._failure is None
        finally:
            reader.cancel(); await asyncio.gather(reader, return_exceptions=True)
            for queue in real_queues:
                queue.close(); queue.join_thread()
    asyncio.run(run())
