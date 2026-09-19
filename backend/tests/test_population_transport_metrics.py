import asyncio
import json
import subprocess
import sys

import pytest

from scripts.verification.population_benchmark_metrics import LoopbackWebSocketByteProxy, WebSocketStreamCounter


@pytest.mark.skipif(sys.platform not in {"win32", "linux"}, reason="当前 RSS 的固定 runner 采样支持 Windows/Linux")
def test_current_rss_tracks_released_mapping_instead_of_process_peak():
    code = """
import json, mmap
from scripts.verification.population_benchmark_metrics import current_rss_bytes, peak_rss_bytes
size = 32 * 1024 * 1024
memory = mmap.mmap(-1, size)
for offset in range(0, size, 4096):
    memory[offset] = 1
during = current_rss_bytes()
peak = peak_rss_bytes()
memory.close()
after = current_rss_bytes()
print(json.dumps(dict(during=during, peak=peak, after=after)))
"""
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=15)
    values = json.loads(result.stdout)
    assert 0 < values["after"] < values["during"] - 16 * 1024 * 1024
    assert values["peak"] >= values["during"]


def test_segment_metrics_keep_canonical_hash_stable_and_do_not_invent_network_bytes():
    from pydantic import BaseModel
    from scripts.verification.population_benchmark_metrics import measure_population_transport
    class Command(BaseModel):
        seed: int
        actors: list[str]
    source = {"seed": 7, "actors": ["居民", "resident_01"]}
    results = [measure_population_transport(lambda: Command.model_validate(source), scope="internal", audience="backend") for _ in range(3)]
    assert len({result.canonical_sha256 for result in results}) == 1
    assert len({result.encoded_bytes for result in results}) == 1
    assert all(result.pickle_ms is not None and result.alloc_bytes > 0 for result in results)
    assert all(result.sqlite_ms is None and result.application_payload_bytes is None and result.ws_frame_bytes is None and result.handshake_bytes is None for result in results)
    source["actors"].append("changed")
    assert measure_population_transport(lambda: Command.model_validate(source), scope="internal", audience="backend").canonical_sha256 != results[0].canonical_sha256


def test_public_metrics_only_accept_existing_mirror_model_and_never_pickle_client_data():
    from scripts.verification.population_benchmark_metrics import measure_population_transport
    from app.ws_protocol import GameplayMirrorDeliveryEnvelope
    from test_mirror_delta_transport import _message
    message = _message(1)
    result = measure_population_transport(lambda: GameplayMirrorDeliveryEnvelope.model_validate(message["payload"]), scope="public", audience="godot")
    assert result.message_kind == "snapshot" and result.actor_count == 1
    assert result.pickle_ms is None and result.scope == "public" and result.audience == "godot"
    for command, scope, audience in ((b"client-pickle", "internal", "backend"), (lambda: None, "private", "godot")):
        with pytest.raises(ValueError):
            measure_population_transport(command, scope=scope, audience=audience)


def test_raw_tcp_payload_count_handles_split_headers_and_frames_in_same_read():
    counter = WebSocketStreamCounter(response=True)
    header = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"
    frames = b"\x81\x02{}\x89\x00"
    for chunk in (header[:6], header[6:-3], header[-3:] + frames[:2], frames[2:]):
        counter.observe(chunk)
    assert counter.handshake_bytes == len(header)
    assert counter.ws_frame_bytes == len(frames)
    assert counter.upgraded


@pytest.mark.parametrize("payload", [
    b"HTTP/1.1 200 OK\r\n\r\n",
    b"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Extensions: permessage-deflate\r\n\r\n",
    b"x" * 65537,
], ids=["not-upgraded", "compression", "oversized-header"])
def test_non_upgrade_compression_and_unbounded_headers_are_rejected(payload):
    with pytest.raises(ValueError):
        WebSocketStreamCounter(response=True).observe(payload)


def test_real_loopback_proxy_counts_handshake_and_frame_bytes_separately():
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve

    async def run():
        payload = json.dumps({"message_type": "population-test", "text": "居民", "padding": "x" * 70000}, ensure_ascii=False)
        async def echo(socket):
            await socket.send(await socket.recv())
        async with serve(echo, "127.0.0.1", 0, compression=None) as backend:
            port = backend.sockets[0].getsockname()[1]
            async with LoopbackWebSocketByteProxy(port) as proxy:
                async with connect(f"ws://127.0.0.1:{proxy.port}/ws", compression=None) as client:
                    await client.send(payload)
                    assert await client.recv() == payload
                await proxy.wait_closed_connections()
                result = proxy.measurements()
            application_bytes = len(payload.encode("utf-8"))
            assert result["compression"] == "disabled"
            assert result["handshake_bytes"] == sum(result["handshake_bytes_by_direction"].values()) > 100
            # 大于65535的帧：10字节header；客户端另有4字节mask；双方各有close(2字节payload)。
            assert result["ws_frame_bytes_by_direction"]["client_to_backend"] == application_bytes + 14 + 8
            assert result["ws_frame_bytes_by_direction"]["backend_to_client"] == application_bytes + 10 + 4
            assert result["ws_frame_bytes"] == application_bytes * 2 + 36
            assert result["tcp_ip_header_bytes_measured"] is False
    asyncio.run(run())


@pytest.mark.parametrize('exceptional', [False, True])
def test_proxy_context_exit_closes_live_websocket_and_invalidates_partial_counts(exceptional):
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve
    async def run():
        async def hold(socket):
            await socket.wait_closed()
        async with serve(hold, '127.0.0.1', 0, compression=None) as backend:
            proxy = LoopbackWebSocketByteProxy(backend.sockets[0].getsockname()[1])
            client = None
            async def session():
                nonlocal client
                async with proxy:
                    client = await connect(f'ws://127.0.0.1:{proxy.port}', compression=None)
                    if exceptional:
                        raise RuntimeError('probe failed')
            try:
                if exceptional:
                    with pytest.raises(RuntimeError, match='probe failed'):
                        await asyncio.wait_for(session(), 2)
                else:
                    await asyncio.wait_for(session(), 2)
                await asyncio.wait_for(client.wait_closed(), 2)
                assert not proxy._tasks
                with pytest.raises(ValueError, match='websocket_counter_invalid'):
                    proxy.measurements()
            finally:
                if client is not None:
                    await client.close()
                await proxy.wait_closed_connections()
                await proxy.__aexit__(None, None, None)
    asyncio.run(run())


@pytest.mark.parametrize('cancel', [False, True])
def test_proxy_wait_timeout_or_cancellation_never_produces_valid_measurements(cancel):
    from websockets.asyncio.client import connect
    from websockets.asyncio.server import serve
    async def run():
        async def hold(socket):
            await socket.wait_closed()
        async with serve(hold, '127.0.0.1', 0, compression=None) as backend:
            async with LoopbackWebSocketByteProxy(backend.sockets[0].getsockname()[1]) as proxy:
                async with connect(f'ws://127.0.0.1:{proxy.port}', compression=None) as client:
                    waiter = asyncio.create_task(proxy.wait_closed_connections())
                    if cancel:
                        await asyncio.sleep(0)
                        waiter.cancel()
                    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
                        await waiter
                    await asyncio.wait_for(client.wait_closed(), 2)
                    assert not proxy._tasks
                    with pytest.raises(ValueError, match='websocket_counter_invalid'):
                        proxy.measurements()
    asyncio.run(run())


def test_segment_validation_accepts_strict_tuple_json_without_weakening_schema():
    from pydantic import BaseModel, ConfigDict, model_validator
    from scripts.verification.population_benchmark_metrics import measure_population_transport
    validated = []
    class StrictPayload(BaseModel):
        model_config = ConfigDict(strict=True, frozen=True)
        actors: tuple[str, ...]
        @model_validator(mode='after')
        def record(self):
            validated.append(self)
            return self
    model = StrictPayload(actors=('resident_1',))
    result = measure_population_transport(lambda: model, scope='internal', audience='backend')
    assert len(validated) == 2 and validated[1] is not model
    assert validated[1] == model and isinstance(validated[1].actors, tuple)
    assert StrictPayload.model_config['strict'] is True
    assert result.validate_ms >= 0 and result.encoded_bytes > 0


def test_segment_boundary_model_count_counts_distinct_instances_across_both_boundaries():
    from pydantic import BaseModel
    from scripts.verification.population_benchmark_metrics import measure_population_transport
    class Child(BaseModel):
        value: int
    class Pair(BaseModel):
        left: Child
        right: Child
    child = Child(value=1)
    pair = Pair(left=child, right=child)
    assert pair.left is pair.right
    result = measure_population_transport(lambda: pair, scope='internal', audience='backend')
    assert result.boundary_model_count == 5  # 源root+共享child；重验root+两个新child。
