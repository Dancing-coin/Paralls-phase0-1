from __future__ import annotations

import sys

import anyio
import pytest
from starlette.testclient import WebSocketTestSession

from app.config import Settings


async def _receive_websocket_message_with_timeout(stream: object) -> dict[str, object]:
    with anyio.fail_after(5.0):
        return await stream.receive()  # type: ignore[attr-defined, no-any-return]


def _bounded_websocket_receive(self: WebSocketTestSession) -> dict[str, object]:
    try:
        return self.portal.call(_receive_websocket_message_with_timeout, self._send_rx)  # type: ignore[union-attr]
    except TimeoutError as exc:
        raise AssertionError("timed out after 5 seconds waiting for a WebSocket test message") from exc


@pytest.fixture(autouse=True)
def disable_live_siming_llm_for_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.config as config_module
    import app.character_agent.gateway.model_provider as model_provider_module

    test_settings = Settings(
        dialogue_mode="stub",
        character_model_provider_kind="local",
        character_model_endpoint=None,
        character_model_api_key=None,
        character_model_model=None,
        character_model_timeout_seconds=20.0,
        heavenly_graph_path=":memory:",
    )
    current_settings = config_module.settings
    for field_name in Settings.model_fields:
        monkeypatch.setattr(current_settings, field_name, getattr(test_settings, field_name))
    monkeypatch.setattr(config_module, "settings", current_settings)
    monkeypatch.setattr(model_provider_module, "settings", current_settings)
    app_main = sys.modules.get("app.main")
    if app_main is not None:
        monkeypatch.setattr(app_main, "settings", current_settings)
    monkeypatch.setattr(WebSocketTestSession, "receive", _bounded_websocket_receive)
