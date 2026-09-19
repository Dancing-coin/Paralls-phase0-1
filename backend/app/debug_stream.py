from __future__ import annotations

import asyncio
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


@dataclass
class _Subscription:
    loop: asyncio.AbstractEventLoop | None
    pending: deque[dict[str, Any]] = field(default_factory=deque)
    scheduled: bool = False
    closed: bool = False


class DebugStream:
    def __init__(self, max_events: int = 200) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._subscribers: dict[asyncio.Queue, _Subscription] = {}
        self._sequence = 0
        self._lock = RLock()

    def clear(self) -> None:
        with self._lock:
            self._events.clear()
            self._sequence = 0
            for queue, subscription in tuple(self._subscribers.items()):
                subscription.closed = True
                subscription.pending.clear()
                self._schedule(queue, subscription)

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(self._events))

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(event)
        with self._lock:
            self._sequence += 1
            payload["sequence"] = self._sequence
            self._events.append(payload)
            for queue, subscription in tuple(self._subscribers.items()):
                if subscription.closed:
                    continue
                if len(subscription.pending) == 100:
                    subscription.closed = True
                    subscription.pending.clear()
                else:
                    subscription.pending.append(deepcopy(payload))
                self._schedule(queue, subscription)
        return deepcopy(payload)

    def _schedule(self, queue: asyncio.Queue, subscription: _Subscription) -> None:
        # 每个订阅最多一个待执行回调；事件积压不会撑大 loop 的回调队列。
        if subscription.scheduled:
            return
        subscription.scheduled = True
        if subscription.loop is None:
            # 保留无事件循环的离线同步读取接口。
            self._drain(queue, subscription)
        else:
            try:
                subscription.loop.call_soon_threadsafe(self._drain, queue, subscription)
            except RuntimeError:
                self._subscribers.pop(queue, None)

    def _drain(self, queue: asyncio.Queue, subscription: _Subscription) -> None:
        with self._lock:
            if self._subscribers.get(queue) is not subscription:
                return
            subscription.scheduled = False
            while subscription.pending and not subscription.closed:
                try:
                    queue.put_nowait(subscription.pending.popleft())
                except asyncio.QueueFull:
                    subscription.closed = True
            if subscription.closed:
                subscription.pending.clear()
                while not queue.empty():
                    queue.get_nowait()
                # 内部终止信号；WebSocket 关闭后由现有客户端重连、重取历史。
                queue.put_nowait(None)
                self._subscribers.pop(queue, None)

    def subscribe(self) -> asyncio.Queue[dict[str, Any] | None]:
        return self.snapshot_and_subscribe()[1]

    def snapshot_and_subscribe(self) -> tuple[list[dict[str, Any]], asyncio.Queue[dict[str, Any] | None]]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=100)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        with self._lock:
            history = deepcopy(list(self._events))
            self._subscribers[queue] = _Subscription(loop)
        return history, queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers.pop(queue, None)


debug_stream = DebugStream()
