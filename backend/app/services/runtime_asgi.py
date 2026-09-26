"""真实 ASGI transport；整局装配和业务只在原 spawn child 中执行。"""
from contextlib import asynccontextmanager, suppress
import asyncio
import gc
import json
from uuid import uuid4

from anyio import CancelScope
from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app.services.runtime_process import RuntimeProcess, RuntimeProcessError, RUNTIME_HTTP_ROUTE_NAMES
from app.ws_protocol import Envelope
from app.services.process_qos import high_qos


# Uvicorn 0.52 sansio 的 peer-close/退出交错会重复发 Close；使用原受支持实现。
RUNTIME_WEBSOCKET_PROTOCOL = "websockets"

def create_runtime_app(component_app):
    @asynccontextmanager
    async def lifespan(app):
        with high_qos() as policy:
            app.state.process_qos = policy
            from app import main
            # 公共 model_dump 有意隐藏 credential；受信 bootstrap 必须保留实际配置。
            configured = main.settings.model_dump(mode='json')
            for name, field in type(main.settings).model_fields.items():
                if field.exclude:
                    configured[name] = getattr(main.settings, name)
            configured['siming_llm_routes'] = [dict(route.model_dump(mode='json'), api_key=route.api_key)
                for route in main.settings.siming_llm_routes]
            host = RuntimeProcess(json.dumps(configured, ensure_ascii=False, allow_nan=False))
            app.state.runtime_process = host
            try:
                await host.start()
                yield
            finally:
                await host.close()

    app = FastAPI(title=component_app.title, lifespan=lifespan)

    @app.get('/health')
    async def health():
        return app.state.runtime_process.snapshot()

    def http_endpoint(route_name):
        async def dispatch(request: Request):
            host = app.state.runtime_process
            try:
                body = (await request.body()).decode('utf-8')
            except UnicodeDecodeError as error:
                raise HTTPException(400, 'There was an error parsing the body') from error
            try:
                result = await host.request('http.request', dict(route=route_name, method=request.method,
                    path=request.url.path, query=request.scope['query_string'].decode('latin-1'), body=body,
                    headers=[[key.decode('latin-1'), value.decode('latin-1')] for key, value in request.scope['headers']],
                    remote_host=request.client.host if request.client else '',
                    remote_port=request.client.port if request.client else 0))
            except RuntimeProcessError as error:
                raise HTTPException(503, str(error)) from error
            response = Response(content=result['body'], status_code=result['status'])
            response.raw_headers = [(key.encode('latin-1'), value.encode('latin-1')) for key, value in result['headers']]
            return response
        return dispatch

    for route in component_app.routes:
        if route.name in RUNTIME_HTTP_ROUTE_NAMES:
            app.add_api_route(route.path, http_endpoint(route.name), methods=sorted(route.methods), name=route.name)
        elif route.name in {'debug_panel', 'debug_panel_js'}:
            app.add_api_route(route.path, route.endpoint, methods=sorted(route.methods),
                response_class=route.response_class, name=route.name)
    # 保留原 typed HTTP 文档；请求仍必须经上面登记的 route 名与原 child 验证。
    app.openapi = component_app.openapi

    closed_websocket_count = 0

    async def connection(websocket: WebSocket):
        nonlocal closed_websocket_count
        from app import main
        host = app.state.runtime_process
        connection_ref = f'websocket:{uuid4().hex}'
        send_lock = asyncio.Lock()
        await websocket.accept()
        async def send(message):
            async with send_lock:
                await websocket.send_json(message)
        async def close(code, reason):
            with suppress(RuntimeError, WebSocketDisconnect):
                await websocket.close(code=code, reason=reason)
        inbound = asyncio.Queue(128)
        async def receive_frames():
            while True:
                message = await websocket.receive()
                if message['type'] == 'websocket.disconnect':
                    return
                if message.get('text') is None:
                    raise ValueError('websocket_text_required')
                # 等待 bind/owner/send 时仍独立观察 disconnect，缓存严格有界。
                inbound.put_nowait(message['text'])

        async def process_frames():
            await host.connect(connection_ref, path=websocket.url.path, query=dict(websocket.query_params),
                remote_host=websocket.client.host if websocket.client else '', send_json=send, close_socket=close)
            while True:
                text = await inbound.get()
                if websocket.url.path == '/debug/ws':
                    await host.envelope(connection_ref, dict(text=text))
                    continue
                raw = None
                try:
                    raw = json.loads(text)
                    envelope = Envelope.model_validate(raw)
                    if envelope.message_type == 'runtime_enqueue':
                        await host.enqueue_runtime(connection_ref, envelope.payload)
                    else:
                        await host.envelope(connection_ref, raw)
                except (ValidationError, ValueError, TypeError) as error:
                    await send(main._as_error_ack(source_type=str(raw.get('message_type', 'unknown'))
                        if isinstance(raw, dict) else 'unknown', route='invalid_payload', error=error))

        reader = asyncio.create_task(receive_frames())
        worker = asyncio.create_task(process_frames())
        close_reason = None
        try:
            done, _ = await asyncio.wait((reader, worker), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except WebSocketDisconnect:
            pass
        except (RuntimeProcessError, asyncio.QueueFull):
            close_reason = (1013, 'runtime_unavailable')
        except ValueError:
            close_reason = (1003, 'websocket_text_required')
        finally:
            # 先取消尚在等待屏障的输入，再解绑；不让断连后的帧获得执行信用。
            with CancelScope(shield=True):
                reader.cancel()
                worker.cancel()
                await asyncio.gather(reader, worker, return_exceptions=True)
                await host.disconnect(connection_ref)
                if close_reason is not None:
                    await close(*close_reason)
                closed_websocket_count += 1
                if closed_websocket_count % 64 == 0:
                    # Windows Proactor 的关闭 transport 循环引用需及时扫过老代。
                    gc.collect(2)
    app.websocket('/ws')(connection)
    app.websocket('/debug/ws')(connection)
    return app
