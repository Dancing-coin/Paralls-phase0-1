"""群体验证脚本共用的统计口径，不参与运行时决策。"""
from __future__ import annotations

import hashlib
import asyncio
import math
import os
from pathlib import Path
import sqlite3
import sys
from threading import Lock
from dataclasses import dataclass
import json
from time import perf_counter


@dataclass(frozen=True)
class TransportMetrics:
    scope: str
    audience: str
    message_kind: str
    materialize_ms: float
    validate_ms: float
    json_encode_ms: float
    json_decode_ms: float
    pickle_ms: float | None
    hash_ms: float
    sqlite_ms: float | None
    application_payload_bytes: int | None
    ws_frame_bytes: int | None
    handshake_bytes: int | None
    alloc_bytes: int
    canonical_sha256: str
    encoded_bytes: int
    actor_count: int | None
    field_count: int
    boundary_model_count: int


def measure_population_transport(command, *, scope: str, audience: str) -> TransportMetrics:
    """独立测量进程的可信model工厂。scope/audience是画像标签，不授予读取权限。

    计时包含tracemalloc开销，不用作未插桩1×预算；网络和SQLite未观测时明确为None。
    model_count只计两个边界实际保留的Pydantic对象，不冒称统计工厂内部所有临时对象。
    """
    import pickle
    import tracemalloc
    from pydantic import BaseModel
    if not callable(command) or (scope, audience) not in {("internal", "backend"), ("public", "godot")}:
        raise ValueError("trusted_transport_measurement_factory_required")
    if tracemalloc.is_tracing():
        raise ValueError("transport_measurement_requires_isolated_tracer")

    def timed(call):
        start = perf_counter()
        result = call()
        return result, (perf_counter() - start) * 1000

    retained_model_ids = set()

    def models(value):
        if isinstance(value, BaseModel):
            if id(value) in retained_model_ids:
                return 0
            retained_model_ids.add(id(value))
            return 1 + sum(models(item) for item in value.__dict__.values())
        if isinstance(value, dict):
            return sum(models(item) for item in value.values())
        if isinstance(value, (list, tuple)):
            return sum(models(item) for item in value)
        return 0

    def fields(value):
        if isinstance(value, dict):
            return len(value) + sum(fields(item) for item in value.values())
        if isinstance(value, list):
            return sum(fields(item) for item in value)
        return 0

    tracemalloc.start()
    try:
        model, materialize_ms = timed(command)
        if not isinstance(model, BaseModel):
            raise ValueError("transport_measurement_model_required")
        if audience == "godot":
            from app.ws_protocol import GameplayMirrorDeliveryEnvelope
            if not isinstance(model, GameplayMirrorDeliveryEnvelope):
                raise ValueError("public_mirror_envelope_required")
        # JSON边界完整重验：保留strict模型的JSON输入合同，不复用原实例。
        public_or_internal, dump_ms = timed(lambda: model.model_dump(mode="json"))
        encoded, encode_ms = timed(lambda: json.dumps(public_or_internal, ensure_ascii=True, sort_keys=True,
                                                    separators=(",", ":"), allow_nan=False).encode("utf-8"))
        # validate_ms含Pydantic的JSON解析+schema校验；decode_ms是独立stdlib解析对照，不可相加冒称流水线总耗时。
        validated, validate_ms = timed(lambda: type(model).model_validate_json(encoded))
        decoded, decode_ms = timed(lambda: json.loads(encoded))
        checksum, hash_ms = timed(lambda: "sha256:" + hashlib.sha256(encoded).hexdigest())
        pickle_ms = None
        if audience == "backend":
            # 仅可信进程内序列化基准；没有pickle.loads，也不接受客户端pickle输入。
            _, pickle_ms = timed(lambda: pickle.dumps(decoded, protocol=pickle.HIGHEST_PROTOCOL))
        return TransportMetrics(scope=scope, audience=audience,
            message_kind=str(public_or_internal.get("delivery_kind", type(model).__name__)),
            materialize_ms=materialize_ms + dump_ms, validate_ms=validate_ms,
            json_encode_ms=encode_ms, json_decode_ms=decode_ms, pickle_ms=pickle_ms, hash_ms=hash_ms,
            sqlite_ms=None, application_payload_bytes=None, ws_frame_bytes=None, handshake_bytes=None,
            alloc_bytes=tracemalloc.get_traced_memory()[1], canonical_sha256=checksum, encoded_bytes=len(encoded),
            actor_count=1 if public_or_internal.get("actor_ref") else None, field_count=fields(decoded),
            boundary_model_count=models((model, validated)))
    finally:
        tracemalloc.stop()


class WebSocketStreamCounter:
    """统计代理实际转发的TCP payload；仅首次HTTP头暂存，之后不物化frame内容。"""

    def __init__(self, *, response: bool) -> None:
        self.response = response
        self.handshake_bytes = self.ws_frame_bytes = 0
        self.upgraded = False
        self._header = bytearray()

    def observe(self, chunk: bytes) -> None:
        if self.upgraded:
            self.ws_frame_bytes += len(chunk)
            return
        self._header.extend(chunk)
        end = self._header.find(b"\r\n\r\n")
        if end < 0:
            if len(self._header) > 65536:
                raise ValueError("websocket_handshake_too_large")
            return
        end += 4
        if end > 65536:
            raise ValueError("websocket_handshake_too_large")
        lines = bytes(self._header[:end]).lower().split(b"\r\n")
        if (self.response and not lines[0].startswith(b"http/1.1 101 ")) or (not self.response and not lines[0].startswith(b"get ")):
            raise ValueError("websocket_upgrade_required")
        if any(line.split(b":", 1)[0].strip() == b"sec-websocket-extensions" for line in lines[1:] if b":" in line):
            raise ValueError("websocket_compression_must_be_disabled")
        self.handshake_bytes = end
        self.ws_frame_bytes = len(self._header) - end
        self._header.clear()
        self.upgraded = True


class LoopbackWebSocketByteProxy:
    """单次benchmark的一个loopback WS连接；不包含IP/TCP头，不更改业务消息。"""

    def __init__(self, backend_port: int) -> None:
        if not 0 < backend_port < 65536:
            raise ValueError("invalid_loopback_port")
        self.backend_port = backend_port
        self._counters = {"client_to_backend": WebSocketStreamCounter(response=False),
                          "backend_to_client": WebSocketStreamCounter(response=True)}
        self._tasks: set[asyncio.Task] = set()
        self._error: str | None = None
        self._accepted = False
        self._completed = self._closing = False

    async def __aenter__(self):
        self._server = await asyncio.start_server(self._accept, "127.0.0.1", 0)
        self.port = self._server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *_):
        self._closing = True
        self._server.close()
        # Python 3.12 wait_closed 也等活动连接；必须先关闭自己持有的连接。
        tasks = tuple(self._tasks)
        if tasks:
            self._error = self._error or "forced_connection_cleanup"
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.wait_for(self._server.wait_closed(), 2)

    async def _accept(self, client_reader, client_writer):
        task = asyncio.current_task()
        self._tasks.add(task)
        writers = [client_writer]
        pumps = []
        try:
            if self._accepted or self._closing:
                raise ValueError("single_probe_connection_required")
            self._accepted = True
            backend_reader, backend_writer = await asyncio.open_connection("127.0.0.1", self.backend_port)
            writers.append(backend_writer)

            async def forward(reader, writer, counter):
                while chunk := await reader.read(65536):
                    writer.write(chunk)
                    await writer.drain()
                    counter.observe(chunk)
                if writer.can_write_eof():
                    writer.write_eof()

            pumps = [asyncio.create_task(forward(client_reader, backend_writer, self._counters["client_to_backend"])),
                     asyncio.create_task(forward(backend_reader, client_writer, self._counters["backend_to_client"]))]
            await asyncio.gather(*pumps)
            self._completed = True
        except asyncio.CancelledError:
            self._error = self._error or "connection_cancelled"
            raise
        except Exception as error:
            self._error = self._error or type(error).__name__ + ":" + str(error)
        finally:
            try:
                for pump in pumps:
                    pump.cancel()
                await asyncio.gather(*pumps, return_exceptions=True)
                for writer in writers:
                    writer.close()
                try:
                    await asyncio.wait_for(asyncio.gather(*(writer.wait_closed() for writer in writers)), 1)
                except (TimeoutError, OSError) as error:
                    self._error = self._error or "connection_close_failed:" + type(error).__name__
                    for writer in writers:
                        writer.transport.abort()
            except BaseException:
                self._error = self._error or "connection_cleanup_cancelled"
                for writer in writers:
                    writer.transport.abort()
                raise
            finally:
                self._tasks.discard(task)

    async def wait_closed_connections(self) -> None:
        try:
            await asyncio.wait_for(asyncio.gather(*tuple(self._tasks)), 5)
        except (TimeoutError, asyncio.CancelledError):
            self._error = self._error or "connection_wait_interrupted"
            raise

    def measurements(self) -> dict:
        if self._tasks or self._error or not self._completed or not all(counter.upgraded for counter in self._counters.values()):
            raise ValueError("websocket_counter_invalid:" + (self._error or "connection_incomplete"))
        handshakes = {name: counter.handshake_bytes for name, counter in self._counters.items()}
        frames = {name: counter.ws_frame_bytes for name, counter in self._counters.items()}
        return dict(compression="disabled", handshake_bytes=sum(handshakes.values()), ws_frame_bytes=sum(frames.values()),
                    handshake_bytes_by_direction=handshakes, ws_frame_bytes_by_direction=frames,
                    tcp_ip_header_bytes_measured=False)


def percentile(values: list[float], fraction: float = .95) -> float:
    if not values or not 0 < fraction <= 1:
        raise ValueError("invalid_percentile_sample")
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


class SqliteReadMeter:
    """冷启动子进程内统计实际返回行/字节和 VM 步数，不记录 SQL 参数或数据。"""

    def __init__(self, *, vm_interval: int = 100) -> None:
        if vm_interval < 1:
            raise ValueError("invalid_vm_interval")
        self.vm_interval = vm_interval
        self.databases: dict[str, dict[str, int]] = {}
        self._lock = Lock()

    def __enter__(self):
        self._original_connect = sqlite3.connect
        meter = self

        class Cursor(sqlite3.Cursor):
            def _record(self, rows):
                size = sum(len(value.encode("utf-8")) if isinstance(value, str) else len(value)
                           for row in rows for value in row if isinstance(value, (str, bytes)))
                with meter._lock:
                    self.connection.measurements["rows"] += len(rows)
                    self.connection.measurements["payload_bytes"] += size

            def execute(self, *args, **kwargs):
                with meter._lock:
                    self.connection.measurements["statements"] += 1
                return super().execute(*args, **kwargs)

            def executemany(self, *args, **kwargs):
                with meter._lock:
                    self.connection.measurements["statements"] += 1
                return super().executemany(*args, **kwargs)

            def executescript(self, *args, **kwargs):
                with meter._lock:
                    self.connection.measurements["scripts"] += 1
                return super().executescript(*args, **kwargs)

            def fetchone(self):
                row = super().fetchone()
                if row is not None:
                    self._record([row])
                return row

            def fetchmany(self, size=None):
                rows = super().fetchmany() if size is None else super().fetchmany(size)
                self._record(rows)
                return rows

            def fetchall(self):
                rows = super().fetchall()
                self._record(rows)
                return rows

            def __next__(self):
                row = super().__next__()
                self._record([row])
                return row

        class Connection(sqlite3.Connection):
            def cursor(self, factory=Cursor):
                if factory is not Cursor:
                    raise ValueError("unmetered_sqlite_cursor_factory")
                return super().cursor(factory)

            def execute(self, *args, **kwargs):
                return self.cursor().execute(*args, **kwargs)

            def executemany(self, *args, **kwargs):
                return self.cursor().executemany(*args, **kwargs)

            def executescript(self, *args, **kwargs):
                return self.cursor().executescript(*args, **kwargs)

        def connect(database, *args, **kwargs):
            if kwargs.get("factory", sqlite3.Connection) is not sqlite3.Connection:
                raise ValueError("unmetered_sqlite_connection_factory")
            kwargs["factory"] = Connection
            connection = meter._original_connect(database, *args, **kwargs)
            with meter._lock:
                measurements = meter.databases.setdefault(str(database), {
                    "rows": 0, "payload_bytes": 0, "statements": 0, "scripts": 0, "vm_steps_sampled": 0,
                })
            connection.measurements = measurements

            def progress():
                with meter._lock:
                    measurements["vm_steps_sampled"] += meter.vm_interval
                return 0

            connection.set_progress_handler(progress, meter.vm_interval)
            return connection

        sqlite3.connect = connect
        return self

    def __exit__(self, *_):
        sqlite3.connect = self._original_connect

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {"vm_interval": self.vm_interval, "vm_steps_are_sampled": True,
                    "databases": {key: dict(value) for key, value in self.databases.items()}}


def implementation_digest(root: Path) -> str:
    digest = hashlib.sha256()
    paths = [
        *root.joinpath("backend", "app").rglob("*.py"),
        *root.joinpath("scripts", "verification").rglob("*.py"),
    ]
    for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_text(encoding="utf-8").encode("utf-8"))
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _windows_memory():
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "peak_working_set", "working_set", "peak_paged_pool", "paged_pool",
                "peak_nonpaged_pool", "nonpaged_pool", "pagefile", "peak_pagefile",
            )
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters


def current_rss_bytes() -> int:
    """长时趋势必须采当前 resident memory，不能把只增不减的 peak 当 RSS。"""
    if sys.platform == "win32":
        return _windows_memory().working_set
    if sys.platform == "linux":
        return int(Path("/proc/self/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
    raise OSError("current_rss_sampling_unsupported_platform")


def peak_rss_bytes() -> int:
    if sys.platform == "win32":
        return _windows_memory().peak_working_set
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)
