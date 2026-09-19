import asyncio
from threading import Event

import pytest
from starlette.testclient import TestClient

from websocket_test_support import CompletingWebSocketApp


def test_graceful_close_waits_for_actual_asgi_cleanup():
    cleaned = Event()

    async def app(scope, receive, send):
        await receive()
        await send({"type": "websocket.accept"})
        assert (await receive())["type"] == "websocket.disconnect"
        await asyncio.sleep(.01)
        cleaned.set()

    tracked = CompletingWebSocketApp(app)
    with TestClient(tracked).websocket_connect("/ws") as socket:
        tracked.close_and_wait(socket)
        assert cleaned.is_set()


def test_graceful_close_keeps_endpoint_errors_visible():
    async def app(scope, receive, send):
        await receive()
        await send({"type": "websocket.accept"})
        await receive()
        raise ValueError("endpoint failed")

    tracked = CompletingWebSocketApp(app)
    with pytest.raises(ValueError, match="endpoint failed"):
        with TestClient(tracked).websocket_connect("/ws") as socket:
            tracked.close_and_wait(socket)


def test_graceful_close_timeout_is_a_failure():
    class Socket:
        closed = False
        def close(self):
            self.closed = True

    socket = Socket()
    tracked = CompletingWebSocketApp(None)
    with pytest.raises(AssertionError, match="cleanup timed out"):
        tracked.close_and_wait(socket, timeout=.001)
    assert socket.closed
