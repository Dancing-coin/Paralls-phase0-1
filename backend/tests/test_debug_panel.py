from fastapi.testclient import TestClient

from app.debug_narration import build_debug_event
from app.debug_stream import debug_stream
from app.main import app


def test_debug_panel_route_serves_html() -> None:
    client = TestClient(app)
    response = client.get("/debug/panel")

    assert response.status_code == 200
    assert "运行时叙事面板" in response.text


def test_debug_ws_replays_stream_history() -> None:
    debug_stream.clear()
    debug_stream.publish(
        build_debug_event(
            producer_ts=1,
            domain="world",
            stage="l1_raw_fact_ingress",
            summary="玩家进入了 zone_focus。",
            detail={"fact_family": "spatial_access_fact"},
            actor_id="char_c",
        )
    )
    client = TestClient(app)
    with client.websocket_connect("/debug/ws") as websocket:
        first = websocket.receive_json()

    assert first["domain"] == "world"
    assert first["summary"] == "玩家进入了 zone_focus。"
