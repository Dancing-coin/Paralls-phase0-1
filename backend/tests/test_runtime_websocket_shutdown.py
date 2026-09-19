"""真实TCP peer Close 与服务退出交错；不吞协议或lifespan错误。"""
import asyncio
import socket
from app.services.runtime_asgi import RUNTIME_WEBSOCKET_PROTOCOL
import uvicorn
from websockets.asyncio.client import connect

async def app(scope, receive, send):
    if scope['type'] == 'lifespan':
        while True:
            event = await receive()
            if event['type'] == 'lifespan.startup':
                await send({'type': 'lifespan.startup.complete'})
            else:
                await send({'type': 'lifespan.shutdown.complete'})
                return
    else:
        await receive()
        await send({'type': 'websocket.accept'})
        await receive()

async def _run():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.setblocking(False)
        server = uvicorn.Server(uvicorn.Config(app, ws=RUNTIME_WEBSOCKET_PROTOCOL, log_level='error', ws_per_message_deflate=False))
        task = asyncio.create_task(server.serve(sockets=[listener]))
        while not server.started:
            await asyncio.sleep(0.02)
        ws = await connect(f'ws://127.0.0.1:{listener.getsockname()[1]}', proxy=None, compression=None)
        p = next(iter(server.server_state.connections))
        transport = p.transport
        original = p.connection_lost
        entered = asyncio.Event()

        # 暂缓 connection_lost 清理，精确保留 peer Close 后、服务 shutdown 前的窗口。
        def lost(exc):
            entered.set()
        p.connection_lost = lost
        original_shutdown = p.shutdown

        def shutdown():
            try:
                original_shutdown()
            finally:
                original(None)
        p.shutdown = shutdown
        client = asyncio.create_task(ws.close())
        try:
            await asyncio.wait_for(entered.wait(), 3)
            server.should_exit = True
            await asyncio.wait_for(task, 5)
            assert not server.lifespan.startup_failed
            assert not server.lifespan.shutdown_failed and (not server.lifespan.error_occurred)
        finally:
            p.connection_lost = original
            transport.close()
            server.should_exit = True
            await asyncio.gather(task, client, return_exceptions=True)

def test_peer_close_then_shutdown_completes_original_uvicorn_lifecycle():
    asyncio.run(_run())


def test_service_reader_close_precedes_backend_stop_and_retains_remote_failure(tmp_path):
    import ast
    import inspect
    import json
    from scripts.verification import verify_population_service_isolation as probe

    tree = ast.parse(inspect.getsource(probe.load))
    cleanup = next(node.finalbody for node in ast.walk(tree)
                   if isinstance(node, ast.Try) and any(
                       isinstance(item, ast.Expr) and isinstance(item.value, ast.Await)
                       and isinstance(item.value.value, ast.Call)
                       and isinstance(item.value.value.func, ast.Attribute)
                       and item.value.value.func.attr == 'gather' for item in node.body))
    function = ast.AsyncFunctionDef(name='cleanup', args=ast.arguments(
        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
        body=cleanup, decorator_list=[])
    code = compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), '<original-load-cleanup>', 'exec')

    async def scenario(remote_failure):
        directory = tmp_path / str(remote_failure)
        directory.mkdir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.setblocking(False)
            server = uvicorn.Server(uvicorn.Config(app, ws=RUNTIME_WEBSOCKET_PROTOCOL, log_level='error'))
            serving = asyncio.create_task(server.serve(sockets=[listener]))
            while not server.started:
                await asyncio.sleep(.01)
            sockets = [await connect(f'ws://127.0.0.1:{listener.getsockname()[1]}', proxy=None) for _ in range(3)]
            async def read(ws):
                async for _ in ws:
                    pass
            readers = [asyncio.create_task(read(ws)) for ws in sockets]
            class SlowClose:
                async def close(self):
                    # 真实首连接关闭等待期间，后台可以观察原 stop 并开始退出。
                    await asyncio.sleep(.25)
                    await sockets[0].close()
            async def stop_backend():
                while not (directory / 'stop').exists():
                    await asyncio.sleep(.001)
                server.should_exit = True
            stopping = asyncio.create_task(stop_backend())
            result = {'errors': []}
            namespace = dict(directory=directory, read_ws=SlowClose(), fact_ws=sockets[1],
                dialogue_ws=sockets[2], readers=readers, result=result, records=[],
                write_json=probe.write_json, json=json)
            exec(code, namespace)
            try:
                if remote_failure:
                    server.should_exit = True
                    await asyncio.wait_for(serving, 5)
                await asyncio.wait_for(namespace['cleanup'](), 5)
                await asyncio.wait_for(stopping, 5)
                await asyncio.wait_for(serving, 5)
                assert (directory / 'stop').exists()
                if remote_failure:
                    assert result['errors'] == ['reader:ConnectionClosedError'] * 3
                else:
                    assert result['errors'] == []
            finally:
                server.should_exit = True
                stopping.cancel()
                await asyncio.gather(*(ws.close() for ws in sockets), return_exceptions=True)
                await asyncio.gather(serving, stopping, *readers, return_exceptions=True)
    asyncio.run(scenario(False))
    asyncio.run(scenario(True))

    async def close_failure():
        import pytest
        directory = tmp_path / 'close-failure'
        directory.mkdir()
        class BrokenClose:
            async def close(self):
                raise OSError('controlled_close_failure')
        namespace = dict(directory=directory, read_ws=BrokenClose(), fact_ws=None,
                         dialogue_ws=None, readers=[], result={'errors': []}, records=[],
                         write_json=probe.write_json, json=json)
        exec(code, namespace)
        with pytest.raises(OSError, match='controlled_close_failure'):
            await namespace['cleanup']()
        assert (directory / 'stop').exists()
    asyncio.run(close_failure())
