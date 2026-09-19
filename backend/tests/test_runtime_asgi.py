"""生产 ASGI 必须只持 spawn host，原业务在 child 实际执行。"""
import os
import subprocess
import sys
import pytest

from fastapi.testclient import TestClient


def test_production_main_import_does_not_construct_runtime_or_provider_pool():
    result = subprocess.run([sys.executable, '-c',
        'import app.main as m; assert m.runtime_execution is None; assert getattr(m,"runtime",None) is None; '
        'assert m._dialogue_provider_slots is None; assert m.app is not m.component_app'],
        capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_production_app_uses_actual_child_http_ws_and_cached_health(monkeypatch):
    from app import main
    for name, value in dict(heavenly_graph_path=':memory:', dialogue_mode='stub',
            character_model_provider_kind='local', siming_llm_mode='disabled').items():
        monkeypatch.setattr(main.settings, name, value)
    before = {name: vars(main).get(name) for name in ('runtime_execution', 'runtime', '_dialogue_provider_slots')}
    with TestClient(main.app) as client:
        host = main.app.state.runtime_process
        policy = main.app.state.process_qos
        assert policy['pid'] == os.getpid()
        if os.name == 'nt':
            assert policy['applied'][1] & 1 and not policy['applied'][2] & 1
        assert host.process.pid != os.getpid()
        assert all(vars(main).get(name) is value for name, value in before.items())
        health = client.get('/health')
        assert health.status_code == 200 and health.json()['status'] == 'ok'
        assert health.json()['child_pid'] == host.process.pid
        assert client.post('/interaction/orchestrate', json={}).status_code == 422
        assert client.get('/debug/panel').status_code == 200
        with client.websocket_connect('/ws') as socket:
            socket.send_text('{')
            invalid = socket.receive_json()
            assert invalid['message_type'] == 'ack' and invalid['payload']['accepted'] is False
            socket.send_json(dict(message_type='character_actor_status', payload=dict(actor_id='char_a')))
            response = socket.receive_json()
            assert response['message_type'] in {'ack', 'character_actor_status'}
        with client.websocket_connect('/debug/ws') as socket:
            socket.send_text('ping')
    assert policy['restored'] == policy['before']
    assert host.process.exitcode == 0
    assert host.snapshot()['execution_credit']['current'] == 0


@pytest.mark.parametrize("delayed_ready_receipt", [False, True])
def test_actual_asgi_admission_does_not_wait_for_blocked_child_loop(monkeypatch, tmp_path, delayed_ready_receipt):
    from app import main
    import app.services.runtime_process as module
    from test_runtime_process_transport import queued_runtime_child
    monkeypatch.setattr(module, 'CHILD_TARGET', queued_runtime_child)
    release = tmp_path / 'release'
    if delayed_ready_receipt:
        import asyncio
        original_finish = module.RuntimeProcess._finish_delivery
        async def finish(host, value, done):
            if value['message']['message_type'] == 'ready_for_commands':
                # ready 已到 socket，但 child 尚未取得真实 send receipt。
                await asyncio.sleep(.5)
            await original_finish(host, value, done)
        monkeypatch.setattr(module.RuntimeProcess, '_finish_delivery', finish)
        original_enqueue = module.RuntimeProcess.enqueue_runtime
        async def enqueue(host, connection_ref, payload):
            result = await original_enqueue(host, connection_ref, payload)
            if payload['request_id'] == '0':
                await asyncio.sleep(.1)
            return result
        monkeypatch.setattr(module.RuntimeProcess, 'enqueue_runtime', enqueue)
    try:
        with TestClient(main.app) as client:
            with client.websocket_connect('/ws', params={'release_file': str(release)}) as socket:
                try:
                    assert socket.receive_json()['message_type'] == 'ready_for_commands'
                    from time import monotonic, sleep
                    blocked = release.with_name(release.name + '.blocked')
                    deadline = monotonic() + 3
                    while not blocked.exists() and monotonic() < deadline:
                        sleep(.005)
                    assert blocked.exists(), 'child 未进入原同步阻塞切点'
                    for index in range(5):
                        socket.send_json(dict(message_type='runtime_enqueue', payload=dict(request_id=str(index),
                            command=dict(message_type='character_actor_status', payload=dict(actor_id='char_a')))))
                        admission = socket.receive_json()
                        assert admission['message_type'] == 'runtime_admission' and admission['payload']['accepted']
                    assert main.app.state.runtime_process.snapshot()['execution_credit']['current'] >= 5
                    release.touch()
                    completed = [socket.receive_json() for _ in range(5)]
                    assert [row['payload']['request_id'] for row in completed] == list(map(str, range(5)))
                finally:
                    # socket __exit__ 等待 child 断连前，先解除测试自己的同步阻塞。
                    release.touch()
    finally:
        release.touch()


def receive_revocation(socket):
    # 撤权前已送达的认知消息仍可能在客户端队列中，确认以控制帧为准。
    for _ in range(129):
        message = socket.receive_json()
        if message['message_type'] == 'websocket_session_revoked':
            return message
        assert message['message_type'] in {'character_agent_execution', 'character_agent_suggestion'}, message
    raise AssertionError('未在有界通知队列内收到撤权确认')


@pytest.mark.parametrize('queued_types', [(), ('character_agent_execution',),
    ('character_agent_execution', 'character_agent_suggestion')])
def test_revocation_reader_accepts_already_delivered_cognition(queued_types):
    from types import SimpleNamespace
    messages = iter(dict(message_type=kind) for kind in (*queued_types, 'websocket_session_revoked'))
    assert receive_revocation(SimpleNamespace(receive_json=messages.__next__))['message_type'] == 'websocket_session_revoked'


def test_revocation_reader_rejects_unexpected_messages():
    from types import SimpleNamespace
    with pytest.raises(AssertionError):
        receive_revocation(SimpleNamespace(receive_json=lambda: dict(message_type='ack')))


def test_actual_asgi_original_binding_and_raw_authority_completion(monkeypatch):
    from app import main
    import app.services.runtime_process as module
    from test_runtime_process_transport import original_binding_child
    monkeypatch.setattr(module, 'CHILD_TARGET', original_binding_child)
    with TestClient(main.app, client=('127.0.0.1', 47301)) as client:
        with client.websocket_connect('/ws') as socket:
            bound = socket.receive_json()
            assert bound['message_type'] == 'ack' and bound['payload']['accepted'], bound
            assert socket.receive_json()['message_type'] == 'websocket_session_bound'
            socket.send_json(dict(message_type='runtime_enqueue', payload=dict(request_id='raw', command=dict(
                message_type='raw_fact_event', payload=dict(event_type='raw_fact_event', fact_family='spatial_access_fact',
                    fact_type='actor_entered_zone', producer_ts=100, room_id='room_demo', scene_id='scene_demo',
                    zone_id='zone_focus', source=dict(system='godot.raw_fact_emitter', actor_id='char_a'), targets={})))))
            admission, completion = socket.receive_json(), socket.receive_json()
            assert admission['message_type'] == 'runtime_admission' and admission['payload']['accepted']
            assert completion['message_type'] == 'runtime_completion'
            messages = completion['payload']['messages']
            assert any(row['message_type'] == 'spatial_access_runtime_state_snapshot'
                and row['payload']['updated_at'] == 100 for row in messages)
            socket.send_json(dict(message_type='revoke_control', payload={}))
            assert receive_revocation(socket)['message_type'] == 'websocket_session_revoked'
    assert main.app.state.runtime_process.process.exitcode == 0


def http_owner_observation_child(*args):
    import json
    from pathlib import Path
    from threading import get_ident
    from app import main
    from app.services.runtime_process import runtime_child_main
    original = main.InteractionOrchestrationService.execute
    def execute(service, request):
        result = original(service, request)
        Path(main.settings.heavenly_graph_path).with_suffix('.http.json').write_text(json.dumps(dict(
            pid=os.getpid(), thread=get_ident(), owner=main.runtime_execution._owner)), encoding='utf-8')
        return result
    main.InteractionOrchestrationService.execute = execute
    runtime_child_main(*args)


def test_actual_asgi_http_dispatches_original_typed_route_on_child_owner(monkeypatch, tmp_path):
    import json
    from app import main
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', http_owner_observation_child)
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path / 'graph.sqlite3'))
    with TestClient(main.app) as client:
        response = client.post('/interaction/orchestrate', json=dict(intent=dict(intent_id='intent:inspect',
            actor_id='char_a', target_refs=dict(object_ids=['obj_box']), semantic_intent='inspect'),
            player_id='player', target_object_id='obj_box', producer_ts=1))
        assert response.status_code == 200, response.text
        observed = json.loads((tmp_path / 'graph.http.json').read_text(encoding='utf-8'))
        assert observed['pid'] == main.app.state.runtime_process.process.pid != os.getpid()
        assert observed['thread'] == observed['owner']
    assert main.app.state.runtime_process.process.exitcode == 0


def test_actual_asgi_child_death_closes_socket_and_health_without_restart():
    import pytest
    from starlette.websockets import WebSocketDisconnect
    from app import main
    with TestClient(main.app) as client:
        host = main.app.state.runtime_process
        original_pid = host.process.pid
        with client.websocket_connect('/ws') as socket:
            socket.send_json(dict(message_type='character_actor_status', payload=dict(actor_id='char_a')))
            socket.receive_json()
            host.process.terminate()
            host.process.join(3)
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
            assert client.get('/health').json()['status'] == 'unhealthy'
            assert host.process.pid == original_pid
    assert not host.process.is_alive()


def bootstrap_secret_observation_child(*args):
    from pathlib import Path
    from app import main
    from app.services.runtime_process import runtime_child_main
    original = main._start_population_runtime_on_startup
    async def startup():
        # 只验证受控测试值，不输出任何 credential。
        assert all(getattr(main.settings, name) == 'controlled-test-value' for name, field in
            type(main.settings).model_fields.items() if field.exclude)
        assert main.settings.siming_llm_routes[0].api_key == 'controlled-route-value'
        await original()
        Path(main.settings.heavenly_graph_path).with_suffix('.settings-ok').touch()
    main._start_population_runtime_on_startup = startup
    runtime_child_main(*args)


def test_bootstrap_preserves_excluded_settings_and_real_http_enrollment(monkeypatch, tmp_path):
    from app import main
    from app.config import SimingLlmRouteSettings, GameplayMirrorTrustedLocalLaunchProfileSettings
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', bootstrap_secret_observation_child)
    for name, field in type(main.settings).model_fields.items():
        if field.exclude:
            monkeypatch.setattr(main.settings, name, 'controlled-test-value')
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path/'graph.sqlite3'))
    monkeypatch.setattr(main.settings, 'siming_llm_routes', [SimingLlmRouteSettings(
        route_id='controlled', provider='disabled', api_key='controlled-route-value')])
    monkeypatch.setattr(main.settings, 'gameplay_mirror_trusted_local_launch_profiles', [
        GameplayMirrorTrustedLocalLaunchProfileSettings(profile_ref='controlled', principal_ref='player',
            allowed_actor_refs=('character:char_a',), credential_ttl_seconds=60)])
    with TestClient(main.app, client=('127.0.0.1', 47302)) as client:
        assert (tmp_path/'graph.settings-ok').exists()
        response = client.post('/internal/trusted-local-gameplay-mirror-enrollment',
            headers={'X-Gameplay-Mirror-Launcher-Secret':'controlled-test-value'}, json={'launch_profile_ref':'controlled'})
        assert response.status_code == 200
        assert 'controlled-test-value' not in client.get('/health').text


@pytest.mark.parametrize('mode', ['disconnect', 'full', 'connecting'])
def test_asgi_disconnect_cancels_waiting_enqueue_before_prior_barrier_finishes(mode):
    import asyncio
    import json
    from types import SimpleNamespace
    from app import main
    from app.services.runtime_asgi import create_runtime_app
    async def run():
        entered, release, disconnected = asyncio.Event(), asyncio.Event(), asyncio.Event()
        executed = []
        async def connect(*args, **kwargs):
            if mode == 'connecting':
                entered.set()
                await release.wait()
        async def envelope(*args): pass
        async def enqueue(*args):
            entered.set()
            await release.wait()
            executed.append('queued')
        async def disconnect(*args): disconnected.set()
        app = create_runtime_app(main.component_app)
        app.state.runtime_process = SimpleNamespace(connect=connect, envelope=envelope,
            enqueue_runtime=enqueue, disconnect=disconnect)
        inbound = asyncio.Queue()
        async def receive(): return await inbound.get()
        async def send(message): pass
        scope = dict(type='websocket', asgi={'version':'3.0'}, scheme='ws', path='/ws', raw_path=b'/ws',
            query_string=b'', headers=[], client=('127.0.0.1', 1234), server=('localhost',80), subprotocols=[])
        task = asyncio.create_task(app(scope, receive, send))
        inbound.put_nowait({'type':'websocket.connect'})
        for kind in ('character_actor_status', 'runtime_enqueue'):
            inbound.put_nowait(dict(type='websocket.receive', text=json.dumps(dict(message_type=kind, payload={}))))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            if mode == 'full':
                for _ in range(129):
                    inbound.put_nowait(dict(type='websocket.receive', text='{}'))
            else:
                inbound.put_nowait(dict(type='websocket.disconnect', code=1000))
            await asyncio.wait_for(disconnected.wait(), .2)
            assert not executed
        finally:
            release.set()
            await asyncio.wait_for(task, 2)
    asyncio.run(run())


def test_blocked_child_probe_releases_before_socket_exit_on_assertion(monkeypatch, tmp_path):
    from contextlib import contextmanager
    observed = []
    class Socket:
        def receive_json(self):
            return {'message_type': 'controlled_wrong_ready'}
    class Client:
        @contextmanager
        def websocket_connect(self, *args, **kwargs):
            try:
                yield Socket()
            finally:
                observed.append((tmp_path / 'release').exists())
    @contextmanager
    def client(*args, **kwargs):
        yield Client()
    monkeypatch.setattr(sys.modules[__name__], 'TestClient', client)
    with pytest.raises(AssertionError):
        test_actual_asgi_admission_does_not_wait_for_blocked_child_loop(monkeypatch, tmp_path, False)
    assert observed == [True]
