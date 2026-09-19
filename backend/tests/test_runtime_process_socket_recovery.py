"""真实 Uvicorn/WS：旧 owner 退出后显式重启，旧发送不能污染重新授权的连接。"""
import asyncio
from contextlib import asynccontextmanager
import json
import socket

import httpx
import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed


def test_real_socket_owner_restart_fences_old_pending_completion(monkeypatch, tmp_path):
    from app import main
    from app.config import Settings, GameplayMirrorTrustedLocalLaunchProfileSettings
    from app.services import runtime_asgi
    from app.services.runtime_process import RuntimeProcess

    monkeypatch.setattr(main, 'settings', Settings(heavenly_graph_path=str(tmp_path / 'graph.sqlite3'),
        character_model_provider_kind='local', dialogue_mode='stub', siming_llm_mode='disabled',
        gameplay_mirror_launcher_bootstrap_secret='local-test-secret',
        gameplay_mirror_trusted_local_launch_profiles=[GameplayMirrorTrustedLocalLaunchProfileSettings(
            profile_ref='socket-recovery', principal_ref='socket-recovery',
            allowed_actor_refs=('character:char_a',), credential_ttl_seconds=300)]))

    async def run():
        entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
        original_send = runtime_asgi.WebSocket.send_json
        original_finish = RuntimeProcess._finish_delivery
        old_send_results = []

        async def send(websocket, message, *args, **kwargs):
            if message.get('message_type') == 'runtime_completion' and message['payload']['request_id'] == 'old-fact':
                entered.set()
                while not release.is_set():
                    try:
                        await release.wait()
                    except asyncio.CancelledError:
                        # 真实断连链可以多次取消；旧写只由显式 release 结束。
                        cancelled.set()
            return await original_send(websocket, message, *args, **kwargs)

        async def finish(host, value, done):
            if value['message'].get('payload', {}).get('request_id') == 'old-fact':
                old_send_results.append('failed' if done.cancelled() else done.result())
            return await original_finish(host, value, done)

        monkeypatch.setattr(runtime_asgi.WebSocket, 'send_json', send)
        monkeypatch.setattr(RuntimeProcess, '_finish_delivery', finish)

        @asynccontextmanager
        async def server(app):
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                listener.listen(128)
                listener.setblocking(False)
                instance = uvicorn.Server(uvicorn.Config(app, ws=runtime_asgi.RUNTIME_WEBSOCKET_PROTOCOL, access_log=False, log_level='error', ws_per_message_deflate=False))
                task = asyncio.create_task(instance.serve(sockets=[listener]))
                try:
                    async with asyncio.timeout(20):
                        while not instance.started:
                            if task.done():
                                await task
                                raise AssertionError('ASGI startup failed')
                            await asyncio.sleep(.01)
                    yield listener.getsockname()[1], app.state.runtime_process
                finally:
                    release.set()
                    instance.should_exit = True
                    await asyncio.wait_for(task, 20)
                    assert not instance.lifespan.startup_failed and not instance.lifespan.shutdown_failed
                    assert not instance.lifespan.error_occurred

        async def bound(port, ws, http):
            enrollment = await http.post(f'http://127.0.0.1:{port}/internal/trusted-local-gameplay-mirror-enrollment',
                headers={'X-Gameplay-Mirror-Launcher-Secret': 'local-test-secret'}, json={'launch_profile_ref': 'socket-recovery'})
            assert enrollment.status_code == 200
            await ws.send(json.dumps(dict(message_type='websocket_session_bind', payload=enrollment.json())))
            assert json.loads(await asyncio.wait_for(ws.recv(), 5))['payload']['accepted']
            assert json.loads(await asyncio.wait_for(ws.recv(), 5))['message_type'] == 'websocket_session_bound'

        async def fact(ws, request_id, tick):
            await ws.send(json.dumps(dict(message_type='runtime_enqueue', payload=dict(request_id=request_id,
                command=dict(message_type='raw_fact_event', payload=dict(event_type='raw_fact_event',
                    fact_family='spatial_access_fact', fact_type='actor_entered_zone', producer_ts=tick,
                    room_id='room_demo', scene_id='scene_demo', zone_id='zone_focus',
                    source=dict(system='godot.raw_fact_emitter', actor_id='char_a'), targets={}))))))
            admission = json.loads(await asyncio.wait_for(ws.recv(), 5))
            assert admission['message_type'] == 'runtime_admission' and admission['payload']['accepted']

        async with httpx.AsyncClient(trust_env=False) as http:
            async with server(main.app) as (old_port, old):
                async with connect(f'ws://127.0.0.1:{old_port}/ws', compression=None, proxy=None) as old_ws:
                    await bound(old_port, old_ws, http)
                    await fact(old_ws, 'old-fact', 111)
                    await asyncio.wait_for(entered.wait(), 5)
                    assert old.snapshot()['runtime_pending'] == 1 and old.snapshot()['pending_send'] == 1
                    old_generation, old_pid = old._generation, old.process.pid
                    old.process.terminate()
                    await asyncio.to_thread(old.process.join, 5)
                    assert not old.process.is_alive() and old.process.exitcode != 0
                    await asyncio.wait_for(cancelled.wait(), 5)
                    with pytest.raises(ConnectionClosed):
                        await asyncio.wait_for(old_ws.recv(), 5)
                    health = await http.get(f'http://127.0.0.1:{old_port}/health')
                    assert health.json()['status'] == 'unhealthy'
                    assert old.snapshot()['runtime_pending'] == 0

                    # 使用原生产 app 工厂明确重启；同库新 owner 必须重新签发并绑定。
                    async with server(runtime_asgi.create_runtime_app(main.component_app)) as (port, current):
                        assert current._generation != old_generation and current.process.pid != old_pid
                        async with connect(f'ws://127.0.0.1:{port}/ws', compression=None, proxy=None) as ws:
                            await bound(port, ws, http)
                            await fact(ws, 'new-fact', 222)
                            completion = json.loads(await asyncio.wait_for(ws.recv(), 5))
                            assert completion['message_type'] == 'runtime_completion'
                            assert completion['payload']['request_id'] == 'new-fact'
                            assert completion['payload']['status'] == 'owner_finished'
                            assert any(message['message_type'] == 'spatial_access_runtime_state_snapshot'
                                and message['payload']['updated_at'] == 222 for message in completion['payload']['messages'])
                            assert not release.is_set()
                            assert old_send_results == []
                            assert old.snapshot()['pending_send'] == 1
                            release.set()
                            async with asyncio.timeout(5):
                                while not old_send_results:
                                    await asyncio.sleep(.01)
                            assert old_send_results == ['failed']
                            deadline = asyncio.get_running_loop().time() + .2
                            while (remaining := deadline - asyncio.get_running_loop().time()) > 0:
                                try:
                                    followup = json.loads(await asyncio.wait_for(ws.recv(), remaining))
                                except TimeoutError:
                                    break
                                # 原 raw fact 的合法 cognition 后续仍可发送，旧 completion 不能出现。
                                assert followup['message_type'] != 'runtime_completion'
                                assert followup.get('payload', {}).get('request_id') != 'old-fact'
                            assert (await http.get(f'http://127.0.0.1:{port}/health')).json()['status'] == 'ok'
                    assert current.process.exitcode == 0
        assert old.snapshot()['pending_send'] == 0

    asyncio.run(run())
