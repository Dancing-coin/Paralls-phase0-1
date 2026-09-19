from threading import Event


class CompletingWebSocketApp:
    """单个 WebSocket 测试显式等真实 endpoint 退出，避免 TestClient 提前取消清理。"""

    def __init__(self, app):
        self.app = app
        self.finished = Event()

    async def __call__(self, scope, receive, send):
        try:
            await self.app(scope, receive, send)
        finally:
            if scope["type"] == "websocket":
                self.finished.set()

    def close_and_wait(self, socket, *, timeout=5):
        socket.close()
        assert self.finished.wait(timeout), "WebSocket endpoint cleanup timed out"
