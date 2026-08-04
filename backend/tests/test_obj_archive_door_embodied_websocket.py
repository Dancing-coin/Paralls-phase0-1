from __future__ import annotations

from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
import app.main as main


def _connection(connection_ref: str) -> WebSocketConnectionContext:
    return WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=100,
        connection_ref=connection_ref,
    )


def _bind(connection_context: WebSocketConnectionContext) -> None:
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="char_c",
        controller_instance_id="controller:char_c:door-ws",
        issued_at=100,
        expires_at=200,
    )
    main._handle_envelope(
        Envelope(
            message_type="embodied_controller_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "actor_id": "char_c",
                "controller_instance_id": "controller:char_c:door-ws",
                "protocol_version": 1,
            },
        ),
        connection_context=connection_context,
    )


def test_archive_door_route_rejects_terminal_outcome_from_a_different_connection() -> None:
    main.reset_runtime_state()
    first_connection = _connection("ws_connection:door-one")
    second_connection = _connection("ws_connection:door-two")
    _bind(first_connection)
    main.runtime._actor_positions["char_c"] = (0.0, 1.2, -3.1)  # type: ignore[attr-defined]

    preflight = main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 110,
                "target_object_id": "obj_archive_door",
                "interaction_type": "open",
            },
        ),
        connection_context=first_connection,
    )
    embodied_action_request = next(message for message in preflight if message.get("message_type") == "embodied_action_request")
    grant = embodied_action_request["payload"]["grant"]

    rejected = main._handle_envelope(
        Envelope(
            message_type="embodied_local_outcome",
            payload={
                "interaction_attempt_id": embodied_action_request["payload"]["request"]["interaction_attempt_id"],
                "phase": "terminal",
                "terminal_status": "contact_observed",
                "observed_at": 130,
                "actor_pose_ref": "pose:char_c:door-open",
                "target_binding_ref": "binding:obj_archive_door:1",
                "contact_observation": {
                    "contact_ref": "contact:attempt:obj_archive_door:1",
                    "actor_contact_ref": "collider:char_c:hand_r",
                    "target_collider_ref": "collider:obj_archive_door:body",
                    "contact_window_ref": "window:door-open:1",
                },
                "object_observation": {
                    "object_ref": "obj_archive_door",
                    "previous_state": "closed",
                    "observed_state": "open",
                    "observation_rule_ref": "observation_rule:obj_archive_door:open:v1",
                },
                "trace_refs": ["trace:door:terminal"],
                "causation_id": "interact:110",
                "correlation_id": "interact:110",
                "controller_grant_id": grant["grant_id"],
                "connection_epoch": grant["connection_epoch"],
                "terminal_sequence": 3,
                "outcome_nonce": grant["one_time_outcome_nonce"],
                "payload_digest": "sha256:door-terminal",
            },
        ),
        connection_context=second_connection,
    )

    assert rejected == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": False,
                "source_type": "embodied_local_outcome",
                "route": "embodied_execution_ingress",
                "error_code": "controller_binding_required",
            },
        }
    ]
