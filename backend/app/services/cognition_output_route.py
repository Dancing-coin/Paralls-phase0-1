"""原 WS 来源的短期路由；业务完成与文本传输分离，重启不猜测新连接。"""
from collections import OrderedDict
from dataclasses import dataclass
import asyncio
import json
from threading import Lock
from time import time


@dataclass(frozen=True)
class CognitionOrigin:
    connection_ref: str
    binding_pin: tuple


class CognitionOutputRoutes:
    def __init__(self, *, capacity=256, clock=time):
        self.capacity, self.clock = capacity, clock
        self.sources = OrderedDict()
        self.connections = {}

    def remember(self, event_id, origin, expires_at):
        self.prune()
        if origin is None or event_id in self.sources:
            return
        if len(self.sources) >= self.capacity:
            self.sources.popitem(last=False)
        self.sources[event_id] = (origin, expires_at)

    def prune(self):
        for key, (_, expires) in tuple(self.sources.items()):
            if self.clock() >= expires:
                self.sources.pop(key)

    def resolve(self, event_id):
        self.prune()
        record = self.sources.get(event_id)
        return record[0] if record else None

    def disconnect(self, connection_ref):
        sink = self.connections.get(connection_ref)
        if sink is not None:
            sink.close()
            self.release(connection_ref, sink)
        for key, (origin, _) in tuple(self.sources.items()):
            if origin.connection_ref == connection_ref:
                self.sources.pop(key)

    def release(self, connection_ref, sink):
        if sink.closed and not sink.pending and self.connections.get(connection_ref) is sink:
            self.connections.pop(connection_ref)


class CognitionOutputSink:
    def __init__(self, *, deliver, capacity=32):
        self.loop = asyncio.get_running_loop()
        self.deliver, self.capacity = deliver, capacity
        self.lock = Lock()
        self.pending = 0
        self.closed = False

    def post(self, payload):
        encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
        with self.lock:
            if self.closed or self.pending >= self.capacity:
                return False
            self.pending += 1
            try:
                self.loop.call_soon_threadsafe(self._deliver, encoded)
            except RuntimeError:
                self.pending -= 1
                return False
            return True

    def _deliver(self, encoded):
        # 容量覆盖排队和正在发送，完成回调才释放。
        self.deliver(json.loads(encoded), self.done, self.closed)

    def done(self):
        with self.lock:
            self.pending -= 1

    def close(self):
        with self.lock:
            self.closed = True
