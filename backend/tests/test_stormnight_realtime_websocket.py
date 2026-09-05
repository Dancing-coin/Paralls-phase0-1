from __future__ import annotations

from app import main
from app.ws_protocol import Envelope
from fastapi.testclient import TestClient


def _send(payload: dict[str, object]) -> list[dict[str, object]]:
    return main._handle_envelope(Envelope(message_type="stormnight_player_intent", payload=payload))


def test_stormnight_websocket_returns_committed_projection_for_finite_player_intent() -> None:
    main.reset_runtime_state()
    responses = _send({"kind": "start", "request_id": "ws-start"})
    assert responses[0]["message_type"] == "stormnight_case_projection"
    assert responses[0]["payload"]["accepted"] is True
    assert responses[0]["payload"]["projection"]["opened"] is True


def test_stormnight_websocket_rejects_actor_impersonation_and_unknown_fields() -> None:
    main.reset_runtime_state()
    before = len(main.gameplay_event_store.read_events())
    impersonation = _send({"kind": "start", "request_id": "ws-bad", "actor_ref": "character:stormnight-guardian@1"})
    assert impersonation[0]["message_type"] == "stormnight_case_projection"
    assert impersonation[0]["payload"]["error_code"] == "stormnight_player_actor_forbidden"
    assert len(main.gameplay_event_store.read_events()) == before
    malformed = _send({"kind": "start", "request_id": "ws-extra", "owner_ref": "authority:forged"})
    assert malformed[0]["message_type"] == "ack"
    assert malformed[0]["payload"]["accepted"] is False


def test_stormnight_websocket_changed_duplicate_is_rejected_without_append() -> None:
    main.reset_runtime_state()
    assert _send({"kind": "start", "request_id": "same"})[0]["payload"]["accepted"] is True
    before = len(main.gameplay_event_store.read_events())
    changed = _send({"kind": "inspect", "request_id": "same"})
    assert changed[0]["payload"]["error_code"] == "stormnight_player_idempotency_reused"
    assert len(main.gameplay_event_store.read_events()) == before


def test_stormnight_realtime_intent_round_trips_over_the_actual_websocket() -> None:
    main.reset_runtime_state()
    with TestClient(main.app) as client:
        with client.websocket_connect("/ws") as websocket:
            websocket.send_json({"message_type": "stormnight_player_intent", "payload": {"kind": "start", "request_id": "live-start"}})
            response = websocket.receive_json()
    assert response["message_type"] == "stormnight_case_projection"
    assert response["payload"]["accepted"] is True
    assert response["payload"]["projection"]["opened"] is True
