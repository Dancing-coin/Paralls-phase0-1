from fastapi.testclient import TestClient

from app.debug_narration import build_debug_event
from app.debug_stream import debug_stream
from app.main import _emit_debug_from_messages, app


def test_debug_panel_route_serves_html() -> None:
    client = TestClient(app)
    response = client.get("/debug/panel")

    assert response.status_code == 200
    assert "运行时叙事面板" in response.text
    assert "按域筛选" in response.text
    assert "按角色筛选" in response.text
    assert "最近 5 条动态" in response.text


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


def test_debug_ws_replays_scheduling_round_state_observatory_event() -> None:
    debug_stream.clear()
    _emit_debug_from_messages(
        [
            {
                "message_type": "character_agent_debug_event",
                "payload": {
                    "actor_id": "char_b",
                    "producer_ts": 6803,
                    "stage": "scheduling_round_state",
                    "summary": "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority",
                    "focus_target": "",
                    "intent_label": "degraded_population",
                    "participants": ["char_b", "char_a"],
                    "detail": {
                        "round_id": 4,
                        "lead_actor_id": "char_b",
                        "active_actor_ids": ["char_b", "char_a"],
                        "round_reason_tags": [
                            "continuity_recovery",
                            "wake_up_signal",
                            "salience_priority",
                        ],
                    },
                },
            }
        ]
    )

    client = TestClient(app)
    with client.websocket_connect("/debug/ws") as websocket:
        first = websocket.receive_json()

    assert first["domain"] == "character"
    assert first["stage"] == "scheduling_round_state"
    assert first["actor_id"] == "char_b"
    assert first["detail"]["detail"]["round_id"] == 4


def test_debug_ws_replays_script_beat_event_for_scheduling_round_summary() -> None:
    debug_stream.clear()
    _emit_debug_from_messages(
        [
            {
                "message_type": "script_beat_event",
                "payload": {
                    "beat_id": "beat-corr-1-1",
                    "producer_ts": 6803,
                    "causation_id": "siming:round-event:1",
                    "correlation_id": "corr-1",
                    "participants": ["char_b", "char_a"],
                    "dramatic_summary": "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority",
                    "actor_summaries": [
                        {
                            "actor_id": "char_b",
                            "stage": "scheduling_round_state",
                            "summary": "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority",
                        }
                    ],
                },
            }
        ]
    )

    client = TestClient(app)
    with client.websocket_connect("/debug/ws") as websocket:
        first = websocket.receive_json()

    assert first["domain"] == "world"
    assert first["stage"] == "script_beat_event"
    assert first["summary"] == "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority"


def test_debug_ws_replays_scheduling_round_trace_event() -> None:
    debug_stream.clear()
    _emit_debug_from_messages(
        [
            {
                "message_type": "scheduling_round_trace",
                "payload": {
                    "round_id": 4,
                    "round_started_at": 6803,
                    "lead_actor_id": "char_b",
                    "active_actor_ids": ["char_b", "char_a"],
                    "round_reason_tags": [
                        "continuity_recovery",
                        "wake_up_signal",
                        "salience_priority",
                    ],
                    "round_summary": "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority",
                },
            }
        ]
    )

    client = TestClient(app)
    with client.websocket_connect("/debug/ws") as websocket:
        first = websocket.receive_json()

    assert first["domain"] == "world"
    assert first["stage"] == "scheduling_round_trace"
    assert first["summary"] == "round 4 selects char_b, char_a because continuity_recovery, wake_up_signal, salience_priority"
    assert first["detail"]["round_id"] == 4
