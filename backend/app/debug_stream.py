from __future__ import annotations

import asyncio
from collections import deque
from typing import Any


class DebugStream:
    def __init__(self, max_events: int = 200) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max_events)
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._sequence = 0

    def clear(self) -> None:
        self._events.clear()
        self._sequence = 0

    def history(self) -> list[dict[str, Any]]:
        return list(self._events)

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        payload = dict(event)
        self._sequence += 1
        payload["sequence"] = self._sequence
        self._events.append(payload)
        stale: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)
        return payload

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)


debug_stream = DebugStream()
