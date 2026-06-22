from app.models.player_input import DialogueSubmit
from app.models.ai_output import DialogueResponse
from app.models.environment_request import EnvironmentRequest
from app.models.runtime_state import CharacterRuntimeStateDelta, CharacterRuntimeStateSnapshot
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.models.state_machine_transition import StateMachineTransitionEvent
from app.models.world_result import (
    ActionResolutionResult,
    BodyStateResult,
    ConstraintStateResult,
    EnvironmentStateResult,
    ObjectStateResult,
)
from app.models.siming_output import NarrativeNudge
from fastapi.testclient import TestClient
from app.main import app, reset_runtime_state
from app.l6.authority_bus.router import handle_envelope_entry
from app.ws_protocol import Envelope


def test_player_input_dialogue_submit_shape() -> None:
    event = DialogueSubmit(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="dialogue_submit",
        producer_ts=123,
        target_actor_id="char_a",
        content="Hello",
    )
    assert event.target_actor_id == "char_a"
    assert event.content == "Hello"


def test_ai_output_dialogue_response_shape() -> None:
    event = DialogueResponse(
        actor_id="char_a",
        room_id="room_demo",
        output_type="dialogue_response",
        causation_id="evt1",
        producer_ts=456,
        target_actor_id="char_c",
        content="Hi there",
        tone="neutral",
        tts_required=True,
    )
    assert event.tts_required is True


def test_environment_request_shape() -> None:
    event = EnvironmentRequest(
        request_id="envreq:900",
        candidate_ref="cand_light_drop",
        decision_ref="decision_light_drop",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
        target_entity_refs={"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
        goal="reduce visibility near the letter",
        requested_change_type="light_level_drop",
        requested_strength="medium",
        ttl=1500,
        reason_tag="opportunity_window",
        producer_ts=900,
        causation_id="decision:900",
        correlation_id="decision:900",
    )

    assert event.request_id == "envreq:900"
    assert event.requested_change_type == "light_level_drop"
    assert event.target_entity_refs["environment_ids"] == ["env_lamp"]


def test_world_result_constraint_shape() -> None:
    event = ConstraintStateResult(
        room_id="room_demo",
        source_type="player",
        entity_id="obj_letter",
        target_object_id="obj_letter",
        result_type="constraint_state_result",
        causation_id="evt2",
        producer_ts=789,
        constraint_type="distance_constraint",
        constraint_code="out_of_range",
        constraint_summary="too far",
    )
    assert event.entity_id == "obj_letter"
    assert event.constraint_type == "distance_constraint"
    assert event.constraint_code == "out_of_range"


def test_world_result_action_resolution_shape() -> None:
    event = ActionResolutionResult(
        request_ref="interact:123:obj_letter",
        result_id="action_resolution:interact:123:obj_letter",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        source_type="player",
        entity_id="obj_letter",
        result_type="action_resolution_result",
        causation_id="interact:123",
        correlation_id="interact:123",
        producer_ts=124,
        settlement_status="accepted",
        resolution_status="accepted",
        resolved_entities=["obj_letter"],
        applied_state_changes=["object_state_result", "body_state_result", "environment_state_result"],
        stable_state_summary="interaction accepted",
    )

    assert event.resolution_status == "accepted"
    assert event.request_ref == "interact:123:obj_letter"
    assert event.entity_id == "obj_letter"
    assert event.resolved_entities == ["obj_letter"]


def test_world_result_body_state_shape() -> None:
    event = BodyStateResult(
        request_ref="body:char_c:200",
        result_id="body_result:char_c:200",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        source_type="system",
        result_type="body_state_result",
        causation_id="body:char_c:200",
        correlation_id="body:char_c:200",
        producer_ts=200,
        settlement_status="applied",
        body_state_class="fatigue",
        previous_state="stable",
        current_state="elevated",
        change_summary="fatigue elevated",
    )

    assert event.body_state_class == "fatigue"
    assert event.current_state == "elevated"


def test_self_body_perceived_event_shape() -> None:
    event = SelfBodyPerceivedEvent(
        actor_id="char_c",
        body_state_class="interaction_strain",
        producer_ts=201,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="interaction_strain is engaged",
        source_body_result_id="body_result:char_c:201",
    )

    assert event.event_type == "self_body_perceived_event"
    assert event.actor_id == "char_c"
    assert event.body_state_class == "interaction_strain"


def test_world_result_object_state_shape() -> None:
    event = ObjectStateResult(
        request_ref="object:obj_letter:300",
        result_id="object_result:obj_letter:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        source_type="system",
        entity_id="obj_letter",
        target_object_id="obj_letter",
        result_type="object_state_result",
        causation_id="object:obj_letter:300",
        correlation_id="object:obj_letter:300",
        producer_ts=300,
        settlement_status="applied",
        previous_state="partially_visible",
        current_state="visible",
        change_summary="obj_letter changed from partially_visible to visible",
    )

    assert event.entity_id == "obj_letter"
    assert event.target_object_id == "obj_letter"


def test_world_result_environment_state_shape() -> None:
    event = EnvironmentStateResult(
        request_ref="environment:env_lamp:301",
        result_id="environment_result:env_lamp:301",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        source_type="system",
        entity_id="env_lamp",
        target_environment_id="env_lamp",
        result_type="environment_state_result",
        causation_id="env:env_lamp:alerted",
        correlation_id="env:env_lamp:alerted",
        producer_ts=301,
        settlement_status="applied",
        previous_state="stable",
        current_state="alerted",
        change_summary="env_lamp changed from stable to alerted",
        affected_zone_ids=["zone_focus"],
        field_delta_summary=["light_level", "noise_level", "thermal_level", "smoke_density", "visibility_level"],
        thermal_level="warm",
    )

    assert event.entity_id == "env_lamp"
    assert event.target_environment_id == "env_lamp"
    assert event.thermal_level == "warm"


def test_state_machine_transition_shape() -> None:
    event = StateMachineTransitionEvent(
        event_id="transition:visibility:obj_letter:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        entity_id="obj_letter",
        machine_id="visibility",
        from_state="partially_visible",
        to_state="visible",
        trigger_type="interact.inspect",
        transition_reason="player inspect interaction accepted",
        producer_ts=300,
        causation_id="interact:300",
        correlation_id="interact:300",
    )

    assert event.event_type == "state_machine_transition"
    assert event.entity_id == "obj_letter"
    assert event.machine_id == "visibility"
    assert event.to_state == "visible"


def test_siming_output_narrative_nudge_shape() -> None:
    event = NarrativeNudge(
        room_id="room_demo",
        output_type="narrative_nudge",
        target_actor_id="char_b",
        causation_id="evt3",
        producer_ts=900,
        nudge_summary="pay attention to the letter",
        nudge_intensity="low",
    )
    assert event.nudge_intensity == "low"


def test_character_runtime_state_snapshot_shape() -> None:
    event = CharacterRuntimeStateSnapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        revision_seq=1,
        producer_ts=123,
        current_focus_target="char_a",
        current_attention_source="focus_state",
        nearby_actor_refs=["char_a", "char_b"],
        nearby_object_refs=["obj_letter"],
        nearby_environment_refs=["env_lamp"],
        conversation_candidate_refs=["cand_char_a_letter"],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        updated_at=124,
    )
    assert event.actor_id == "char_c"
    assert event.conversation_candidate_refs == ["cand_char_a_letter"]


def test_character_runtime_state_delta_shape() -> None:
    event = CharacterRuntimeStateDelta(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        revision_seq=2,
        producer_ts=125,
        changed_fields=["current_focus_target", "conversation_candidate_refs", "nearby_environment_refs"],
        current_focus_target="obj_letter",
        nearby_environment_refs=["env_lamp"],
        conversation_candidate_refs=["cand_letter"],
        updated_at=126,
    )
    assert "current_focus_target" in event.changed_fields
    assert event.current_focus_target == "obj_letter"


def test_authority_bus_router_entrypoint_matches_legacy_behavior() -> None:
    reset_runtime_state()
    envelope = Envelope(
        message_type="player_input",
        payload={
            "player_id": "p1",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "actor_id": "char_c",
            "intent_type": "move_intent",
            "producer_ts": 1,
            "move_mode": "locomotion",
            "target_point": [0.0, 0.5, 1.0],
        },
    )

    messages = handle_envelope_entry(envelope)

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["accepted"] is True


def test_websocket_move_intent_emits_ack_and_runtime_snapshot() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 333,
                    "move_mode": "locomotion",
                    "target_point": [1.0, 0.5, 2.0],
                },
            }
        )

        ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "local_motion"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert runtime_snapshot["payload"]["room_id"] == "room_demo"
    assert runtime_snapshot["payload"]["scene_id"] == "scene_demo"
    assert runtime_snapshot["payload"]["zone_id"] == "zone_focus"


def test_websocket_dialogue_submit_emits_ack_and_dialogue_response() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "dialogue_submit",
                    "producer_ts": 123,
                    "target_actor_id": "char_a",
                    "content": "Hello",
                },
            }
        )

        ack = websocket.receive_json()
        response = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "character_service"
    assert response["message_type"] == "dialogue_response"
    assert response["payload"]["actor_id"] == "char_a"


def test_websocket_invalid_player_input_returns_negative_ack_without_dropping_connection() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "bogus",
                    "producer_ts": 124,
                },
            }
        )

        error_ack = websocket.receive_json()

        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 125,
                    "move_mode": "locomotion",
                    "target_point": [1.0, 0.5, 2.0],
                },
            }
        )

        move_ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()

    assert error_ack["message_type"] == "ack"
    assert error_ack["payload"]["accepted"] is False
    assert error_ack["payload"]["route"] == "invalid_payload"
    assert error_ack["payload"]["source_type"] == "player_input"
    assert error_ack["payload"]["error_type"] == "ValueError"
    assert "unsupported intent_type" in error_ack["payload"]["error_message"]
    assert move_ack["message_type"] == "ack"
    assert move_ack["payload"]["accepted"] is True
    assert move_ack["payload"]["route"] == "local_motion"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"


def test_websocket_environment_request_emits_ack_action_resolution_transition_and_environment_state_result() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:500",
                    "candidate_ref": "cand_light_drop",
                    "decision_ref": "decision_light_drop",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "reduce visibility near the letter",
                    "requested_change_type": "light_level_drop",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "opportunity_window",
                    "producer_ts": 500,
                    "causation_id": "decision:500",
                    "correlation_id": "decision:500",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        action_resolution = websocket.receive_json()
        transition = websocket.receive_json()
        environment_result = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "esm_service"
    assert ack["payload"]["source_type"] == "environment_request"
    assert action_request["message_type"] == "action_request"
    assert action_request["event_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "envreq:500"
    assert action_request["payload"]["request_type"] == "environment_request"
    assert action_request["payload"]["source"]["layer"] == "L3"
    assert action_request["payload"]["source"]["system"] == "siming.orchestrator"
    assert action_request["payload"]["target_entity_refs"]["environment_ids"] == ["env_lamp"]
    assert action_resolution["message_type"] == "world_result"
    assert action_resolution["event_type"] == "action_resolution_result"
    assert action_resolution["entity_id"] == "env_lamp"
    assert action_resolution["payload"]["request_ref"] == "envreq:500"
    assert action_resolution["payload"]["entity_id"] == "env_lamp"
    assert action_resolution["payload"]["target_environment_id"] == "env_lamp"
    assert action_resolution["payload"]["resolution_status"] == "accepted"
    assert action_resolution["payload"]["applied_state_changes"] == ["environment_state_result"]
    assert transition["message_type"] == "state_machine_transition"
    assert transition["event_type"] == "state_machine_transition"
    assert transition["entity_id"] == "env_lamp"
    assert transition["machine_id"] == "light_source"
    assert transition["from_state"] == "stable"
    assert transition["to_state"] == "alerted"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["event_type"] == "environment_state_result"
    assert environment_result["entity_id"] == "env_lamp"
    assert environment_result["payload"]["request_ref"] == "envreq:500"
    assert environment_result["payload"]["entity_id"] == "env_lamp"
    assert environment_result["payload"]["target_environment_id"] == "env_lamp"
    assert environment_result["payload"]["machine_id"] == "light_source"
    assert environment_result["payload"]["field_id"] == "field:room_demo:scene_demo:zone_focus"
    assert environment_result["payload"]["source_environment_id"] == "env_lamp"
    assert environment_result["payload"]["field_delta_summary"] == [
        "light_level",
        "noise_level",
        "thermal_level",
        "smoke_density",
        "visibility_level",
    ]
    assert environment_result["payload"]["thermal_level"] == "warm"
    assert environment_result["payload"]["updated_at"] == 502
    assert environment_result["payload"]["current_state"] == "alerted"
    assert environment_result["payload"]["causation_id"] == "decision:500"
    assert environment_result["payload"]["correlation_id"] == "decision:500"


def test_websocket_environment_request_accepts_light_level_restore_variant() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:500a-drop",
                    "candidate_ref": "cand_light_drop",
                    "decision_ref": "decision_light_drop",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "reduce visibility near the letter",
                    "requested_change_type": "light_level_drop",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "window",
                    "producer_ts": 500,
                    "causation_id": "decision:500a-drop",
                    "correlation_id": "decision:500a-drop",
                },
            }
        )
        for _ in range(5):
            websocket.receive_json()
        drop_siming_output = websocket.receive_json()
        drop_character_agent_execution = websocket.receive_json()

        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:500a-restore",
                    "candidate_ref": "cand_light_restore",
                    "decision_ref": "decision_light_restore",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "restore visibility near the letter",
                    "requested_change_type": "light_level_restore",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "window",
                    "producer_ts": 501,
                    "causation_id": "decision:500a-restore",
                    "correlation_id": "decision:500a-restore",
                },
            }
        )

        received = []
        while True:
            message = websocket.receive_json()
            received.append(message)
            message_types = {entry["message_type"] for entry in received}
            world_result_types = {
                entry.get("event_type", "")
                for entry in received
                if entry["message_type"] == "world_result"
            }
            if (
                "ack" in message_types
                and "action_request" in message_types
                and "state_machine_transition" in message_types
                and "action_resolution_result" in world_result_types
                and "environment_state_result" in world_result_types
            ):
                break

    assert drop_siming_output["message_type"] == "siming_output"
    assert drop_siming_output["payload"]["authority_event_type"] == "siming.fact_reveal"
    assert drop_siming_output["payload"]["authority_event_id"].startswith("siming:dispatch_intent:")
    assert drop_siming_output["payload"]["target_environment_id"] == "env_lamp"
    assert drop_character_agent_execution["message_type"] == "character_agent_execution"
    assert drop_character_agent_execution["payload"]["actor_id"] == "char_b"
    ack = next(message for message in received if message["message_type"] == "ack")
    action_request = next(message for message in received if message["message_type"] == "action_request")
    action_resolution = next(
        message
        for message in received
        if message["message_type"] == "world_result"
        and message["event_type"] == "action_resolution_result"
    )
    transition = next(message for message in received if message["message_type"] == "state_machine_transition")
    environment_result = next(
        message
        for message in received
        if message["message_type"] == "world_result"
        and message["event_type"] == "environment_state_result"
    )
    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "envreq:500a-restore"
    assert action_resolution["message_type"] == "world_result"
    assert action_resolution["event_type"] == "action_resolution_result"
    assert action_resolution["payload"]["request_ref"] == "envreq:500a-restore"
    assert transition["message_type"] == "state_machine_transition"
    assert transition["machine_id"] == "light_source"
    assert transition["from_state"] == "alerted"
    assert transition["to_state"] == "stable"
    assert transition["trigger_type"] == "environment_request.light_level_restore"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["event_type"] == "environment_state_result"
    assert environment_result["payload"]["request_ref"] == "envreq:500a-restore"
    assert environment_result["payload"]["machine_id"] == "light_source"
    assert environment_result["payload"]["previous_state"] == "alerted"
    assert environment_result["payload"]["current_state"] == "stable"
    assert environment_result["payload"]["light_level"] == "normal"
    assert environment_result["payload"]["noise_level"] == "quiet"
    assert environment_result["payload"]["thermal_level"] == "neutral"
    assert environment_result["payload"]["smoke_density"] == "clear"
    assert environment_result["payload"]["visibility_level"] == "clear"


def test_websocket_environment_request_accepts_thermal_level_rise_variant() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:500b",
                    "candidate_ref": "cand_heat_rise",
                    "decision_ref": "decision_heat_rise",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "raise thermal pressure near the letter",
                    "requested_change_type": "thermal_level_rise",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "pressure_window",
                    "producer_ts": 500,
                    "causation_id": "decision:500b",
                    "correlation_id": "decision:500b",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        action_resolution = websocket.receive_json()
        transition = websocket.receive_json()
        environment_result = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "envreq:500b"
    assert action_request["payload"]["request_type"] == "environment_request"
    assert action_resolution["message_type"] == "world_result"
    assert action_resolution["event_type"] == "action_resolution_result"
    assert action_resolution["payload"]["request_ref"] == "envreq:500b"
    assert action_resolution["payload"]["resolution_status"] == "accepted"
    assert transition["message_type"] == "state_machine_transition"
    assert transition["machine_id"] == "heat_source"
    assert transition["from_state"] == "stable"
    assert transition["to_state"] == "heated"
    assert transition["trigger_type"] == "environment_request.thermal_level_rise"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["event_type"] == "environment_state_result"
    assert environment_result["payload"]["request_ref"] == "envreq:500b"
    assert environment_result["payload"]["machine_id"] == "heat_source"
    assert environment_result["payload"]["current_state"] == "heated"
    assert environment_result["payload"]["thermal_level"] == "hot"
    assert environment_result["payload"]["light_level"] == "normal"
    assert environment_result["payload"]["noise_level"] == "quiet"
    assert environment_result["payload"]["visibility_level"] == "clear"


def test_websocket_environment_request_accepts_smoke_density_rise_variant() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:500c",
                    "candidate_ref": "cand_smoke_rise",
                    "decision_ref": "decision_smoke_rise",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "raise smoke density near the letter",
                    "requested_change_type": "smoke_density_rise",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "cover_window",
                    "producer_ts": 500,
                    "causation_id": "decision:500c",
                    "correlation_id": "decision:500c",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        action_resolution = websocket.receive_json()
        transition = websocket.receive_json()
        environment_result = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "envreq:500c"
    assert action_request["payload"]["request_type"] == "environment_request"
    assert action_resolution["message_type"] == "world_result"
    assert action_resolution["event_type"] == "action_resolution_result"
    assert action_resolution["payload"]["request_ref"] == "envreq:500c"
    assert action_resolution["payload"]["resolution_status"] == "accepted"
    assert transition["message_type"] == "state_machine_transition"
    assert transition["machine_id"] == "smoke_source"
    assert transition["from_state"] == "stable"
    assert transition["to_state"] == "smoke_rising"
    assert transition["trigger_type"] == "environment_request.smoke_density_rise"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["event_type"] == "environment_state_result"
    assert environment_result["payload"]["request_ref"] == "envreq:500c"
    assert environment_result["payload"]["machine_id"] == "smoke_source"
    assert environment_result["payload"]["current_state"] == "smoke_rising"
    assert environment_result["payload"]["smoke_density"] == "dense"
    assert environment_result["payload"]["visibility_level"] == "reduced"
    assert environment_result["payload"]["light_level"] == "normal"
    assert environment_result["payload"]["noise_level"] == "quiet"
    assert environment_result["payload"]["thermal_level"] == "neutral"


def test_websocket_environment_request_accepts_noise_level_rise_variant() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:500d",
                    "candidate_ref": "cand_noise_rise",
                    "decision_ref": "decision_noise_rise",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "raise noise level near the letter",
                    "requested_change_type": "noise_level_rise",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "mask_window",
                    "producer_ts": 500,
                    "causation_id": "decision:500d",
                    "correlation_id": "decision:500d",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        action_resolution = websocket.receive_json()
        transition = websocket.receive_json()
        environment_result = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "envreq:500d"
    assert action_request["payload"]["request_type"] == "environment_request"
    assert action_resolution["message_type"] == "world_result"
    assert action_resolution["event_type"] == "action_resolution_result"
    assert action_resolution["payload"]["request_ref"] == "envreq:500d"
    assert action_resolution["payload"]["resolution_status"] == "accepted"
    assert transition["message_type"] == "state_machine_transition"
    assert transition["machine_id"] == "noise_source"
    assert transition["from_state"] == "stable"
    assert transition["to_state"] == "noisy"
    assert transition["trigger_type"] == "environment_request.noise_level_rise"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["event_type"] == "environment_state_result"
    assert environment_result["payload"]["request_ref"] == "envreq:500d"
    assert environment_result["payload"]["machine_id"] == "noise_source"
    assert environment_result["payload"]["current_state"] == "noisy"
    assert environment_result["payload"]["noise_level"] == "loud"
    assert environment_result["payload"]["light_level"] == "normal"
    assert environment_result["payload"]["thermal_level"] == "neutral"
    assert environment_result["payload"]["smoke_density"] == "clear"
    assert environment_result["payload"]["visibility_level"] == "clear"


def test_websocket_environment_request_rejects_unsupported_change_type_with_constraint_result() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "environment_request",
                "payload": {
                    "request_id": "envreq:501",
                    "candidate_ref": "cand_heat_rise",
                    "decision_ref": "decision_heat_rise",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {"layer": "L3", "system": "siming.orchestrator", "actor_id": ""},
                    "target_entity_refs": {"actor_ids": [], "object_ids": [], "environment_ids": ["env_lamp"]},
                    "goal": "raise thermal pressure near the letter",
                    "requested_change_type": "thermal_spike",
                    "requested_strength": "medium",
                    "ttl": 1500,
                    "reason_tag": "pressure_test",
                    "producer_ts": 501,
                    "causation_id": "decision:501",
                    "correlation_id": "decision:501",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        constraint_result = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "envreq:501"
    assert action_request["payload"]["request_type"] == "environment_request"
    assert constraint_result["message_type"] == "world_result"
    assert constraint_result["event_type"] == "constraint_state_result"
    assert constraint_result["entity_id"] == "env_lamp"
    assert constraint_result["payload"]["request_ref"] == "envreq:501"
    assert constraint_result["payload"]["constraint_type"] == "unsupported_environment_request"
    assert constraint_result["payload"]["constraint_code"] == "unsupported_change_type"
    assert constraint_result["payload"]["settlement_status"] == "rejected"


def test_websocket_interact_intent_emits_ack_action_resolution_transition_object_state_body_state_environment_shift_and_siming_output() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "interact_intent",
                    "producer_ts": 456,
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        action_resolution = websocket.receive_json()
        transition = websocket.receive_json()
        object_state_result = websocket.receive_json()
        body_state_result = websocket.receive_json()
        self_body_perceived = websocket.receive_json()
        environment_result = websocket.receive_json()
        siming_output = websocket.receive_json()
        character_agent_execution = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        projection_delta = websocket.receive_json()
        candidate_event = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        candidate_siming_output = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["event_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "interact:456:obj_letter"
    assert action_request["payload"]["request_type"] == "interact"
    assert action_request["payload"]["source"]["layer"] == "L1"
    assert action_request["payload"]["source"]["system"] == "player_input_bridge"
    assert action_request["payload"]["target_entity_refs"]["object_ids"] == ["obj_letter"]
    assert action_resolution["message_type"] == "world_result"
    assert action_resolution["event_id"] == "action_resolution:interact:456:obj_letter"
    assert action_resolution["event_type"] == "action_resolution_result"
    assert action_resolution["producer_ts"] == 457
    assert action_resolution["room_id"] == "room_demo"
    assert action_resolution["scene_id"] == "scene_demo"
    assert action_resolution["zone_id"] == "zone_focus"
    assert action_resolution["source"]["layer"] == "L1"
    assert action_resolution["source"]["system"] == "esm"
    assert action_resolution["source"]["actor_id"] == "char_c"
    assert action_resolution["source"]["object_id"] == "obj_letter"
    assert action_resolution["routing"]["audience_mode"] == "authority_broadcast"
    assert action_resolution["routing"]["routing_mode"] == "authoritative_event_bus"
    assert action_resolution["routing"]["dialog_group_id"] is None
    assert action_resolution["routing"]["target_ids"] == []
    assert action_resolution["priority"] == "p1"
    assert action_resolution["ttl"] is None
    assert action_resolution["durability"] == "replayable"
    assert action_resolution["causation_id"] == "interact:456"
    assert action_resolution["correlation_id"] == "interact:456"
    assert action_resolution["entity_id"] == "obj_letter"
    assert action_resolution["payload"]["result_type"] == "action_resolution_result"
    assert action_resolution["payload"]["entity_id"] == "obj_letter"
    assert action_resolution["payload"]["target_object_id"] == "obj_letter"
    assert action_resolution["payload"]["resolution_status"] == "accepted"
    assert action_resolution["payload"]["applied_state_changes"] == [
        "object_state_result",
        "body_state_result",
        "environment_state_result",
    ]
    assert transition["message_type"] == "state_machine_transition"
    assert transition["event_type"] == "state_machine_transition"
    assert transition["entity_id"] == "obj_letter"
    assert transition["machine_id"] == "visibility"
    assert transition["from_state"] == "partially_visible"
    assert transition["to_state"] == "visible"
    assert transition["trigger_type"] == "interact.inspect"
    assert object_state_result["message_type"] == "world_result"
    assert object_state_result["event_type"] == "object_state_result"
    assert object_state_result["entity_id"] == "obj_letter"
    assert object_state_result["payload"]["result_type"] == "object_state_result"
    assert object_state_result["payload"]["entity_id"] == "obj_letter"
    assert object_state_result["payload"]["request_ref"] == "interact:456:obj_letter"
    assert object_state_result["payload"]["causation_id"] == "interact:456"
    assert object_state_result["payload"]["correlation_id"] == "interact:456"
    assert object_state_result["payload"]["target_object_id"] == "obj_letter"
    assert object_state_result["payload"]["machine_id"] == "visibility"
    assert object_state_result["payload"]["current_state"] == "visible"
    assert body_state_result["message_type"] == "world_result"
    assert body_state_result["event_type"] == "body_state_result"
    assert body_state_result["payload"]["result_type"] == "body_state_result"
    assert body_state_result["payload"]["request_ref"] == "interact:456:obj_letter"
    assert body_state_result["payload"]["causation_id"] == "interact:456"
    assert body_state_result["payload"]["correlation_id"] == "interact:456"
    assert body_state_result["payload"]["actor_id"] == "char_c"
    assert body_state_result["payload"]["body_state_class"] == "interaction_strain"
    assert body_state_result["payload"]["current_state"] == "engaged"
    assert self_body_perceived["message_type"] == "self_body_perceived_event"
    assert self_body_perceived["payload"]["actor_id"] == "char_c"
    assert self_body_perceived["payload"]["body_state_class"] == "interaction_strain"
    assert self_body_perceived["payload"]["source_body_result_id"] == "body_result:char_c:460"
    assert environment_result["message_type"] == "world_result"
    assert environment_result["event_type"] == "environment_state_result"
    assert environment_result["entity_id"] == "env_lamp"
    assert environment_result["payload"]["result_type"] == "environment_state_result"
    assert environment_result["payload"]["entity_id"] == "env_lamp"
    assert environment_result["payload"]["request_ref"] == "interact:456:obj_letter"
    assert environment_result["payload"]["causation_id"] == "interact:456"
    assert environment_result["payload"]["correlation_id"] == "interact:456"
    assert environment_result["payload"]["target_environment_id"] == "env_lamp"
    assert environment_result["payload"]["machine_id"] == "light_source"
    assert environment_result["payload"]["field_id"] == "field:room_demo:scene_demo:zone_focus"
    assert environment_result["payload"]["source_environment_id"] == "env_lamp"
    assert environment_result["payload"]["field_delta_summary"] == [
        "light_level",
        "noise_level",
        "thermal_level",
        "smoke_density",
        "visibility_level",
    ]
    assert environment_result["payload"]["thermal_level"] == "warm"
    assert environment_result["payload"]["current_state"] == "alerted"
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_actor_id"] == "char_b"
    assert character_agent_execution["message_type"] == "character_agent_execution"
    assert character_agent_execution["payload"]["actor_id"] == "char_b"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert projection_delta["message_type"] == "character_runtime_state_delta"
    assert projection_delta["payload"]["current_attention_source"] == "world_result"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_object_ids"] == ["obj_letter"]
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_obj_letter"]
    assert candidate_siming_output["message_type"] == "siming_output"
    assert candidate_siming_output["payload"]["target_object_id"] == "obj_letter"


def test_websocket_interact_intent_emits_constraint_when_player_is_far() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 455,
                    "move_mode": "locomotion",
                    "target_point": [0.0, 0.0, 20.0],
                },
            }
        )
        move_ack = websocket.receive_json()
        move_runtime_snapshot = websocket.receive_json()

        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "interact_intent",
                    "producer_ts": 456,
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                },
            }
        )

        ack = websocket.receive_json()
        action_request = websocket.receive_json()
        world_result = websocket.receive_json()

    assert move_ack["message_type"] == "ack"
    assert move_ack["payload"]["route"] == "local_motion"
    assert move_runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert move_runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert ack["message_type"] == "ack"
    assert ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["event_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "interact:456:obj_letter"
    assert action_request["payload"]["request_type"] == "interact"
    assert action_request["payload"]["source"]["system"] == "player_input_bridge"
    assert world_result["message_type"] == "world_result"
    assert world_result["event_type"] == "constraint_state_result"
    assert world_result["source"]["system"] == "esm"
    assert world_result["priority"] == "p1"
    assert world_result["durability"] == "replayable"
    assert world_result["entity_id"] == "obj_letter"
    assert world_result["payload"]["result_type"] == "constraint_state_result"
    assert world_result["payload"]["entity_id"] == "obj_letter"
    assert world_result["payload"]["constraint_type"] == "distance_constraint"
    assert world_result["payload"]["constraint_code"] == "out_of_range"


def test_websocket_interact_intent_emits_constraint_state_when_actor_is_far() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "move_intent",
                    "producer_ts": 455,
                    "move_mode": "locomotion",
                    "target_point": [0.0, 0.0, 16.0],
                },
            }
        )
        move_ack = websocket.receive_json()
        move_runtime_snapshot = websocket.receive_json()
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "interact_intent",
                    "producer_ts": 456,
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                },
            }
        )
        interact_ack = websocket.receive_json()
        action_request = websocket.receive_json()
        world_result = websocket.receive_json()

    assert move_ack["message_type"] == "ack"
    assert move_ack["payload"]["route"] == "local_motion"
    assert move_runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert move_runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert interact_ack["message_type"] == "ack"
    assert interact_ack["payload"]["route"] == "esm_service"
    assert action_request["message_type"] == "action_request"
    assert action_request["event_type"] == "action_request"
    assert action_request["payload"]["request_id"] == "interact:456:obj_letter"
    assert action_request["payload"]["request_type"] == "interact"
    assert action_request["payload"]["source"]["system"] == "player_input_bridge"
    assert world_result["message_type"] == "world_result"
    assert world_result["payload"]["result_type"] == "constraint_state_result"
    assert world_result["payload"]["constraint_type"] == "distance_constraint"
    assert world_result["payload"]["constraint_code"] == "out_of_range"

def test_websocket_focus_target_change_emits_runtime_alignment_messages() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "player_input",
                "payload": {
                    "player_id": "p1",
                    "room_id": "room_demo",
                    "actor_id": "char_c",
                    "intent_type": "focus_target_change",
                    "producer_ts": 789,
                    "target_actor_id": "char_a",
                },
            }
        )

        ack = websocket.receive_json()
        focus_state = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        candidate_event = websocket.receive_json()
        candidate_runtime_delta = websocket.receive_json()
        siming_output = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "character_service"
    assert focus_state["message_type"] == "focus_state"
    assert focus_state["payload"]["actor_id"] == "char_c"
    assert focus_state["payload"]["target_actor_id"] == "char_a"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["scene_id"] == "scene_demo"
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["current_focus_target"] == "char_a"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_actor_ids"] == ["char_a"]
    assert candidate_runtime_delta["message_type"] == "character_runtime_state_delta"
    assert candidate_runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_char_a"]
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_actor_id"] == "char_a"


def test_websocket_raw_visual_fact_event_emits_character_agent_execution_for_char_a() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "raw_fact_event",
                "payload": {
                    "event_type": "raw_fact_event",
                    "fact_family": "visual_fact",
                    "fact_type": "fixed_gaze_on_target",
                    "relation_type": "actor_looks_at_actor",
                    "producer_ts": 901,
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {
                        "layer": "L1",
                        "system": "godot.raw_fact_emitter",
                        "actor_id": "char_c",
                        "object_id": "",
                        "environment_id": "",
                    },
                    "targets": {
                        "actor_id": "char_a",
                        "object_id": "",
                        "environment_id": "",
                    },
                    "world": {},
                    "observability": {"visual": True, "auditory": False, "occluded": False},
                    "acoustics": {},
                    "effect_kind": "pulse",
                    "subject_key": "",
                    "causation_id": "vf:901",
                    "correlation_id": "vf:901",
                },
            }
        )

        received = [websocket.receive_json() for _ in range(8)]

    outputs = [message for message in received if message["message_type"] == "character_agent_output"]
    executions = [message for message in received if message["message_type"] == "character_agent_execution"]

    assert outputs == []
    assert executions
    assert executions[0]["payload"]["actor_id"] == "char_a"
    assert all(message["payload"]["actor_id"] == "char_a" for message in executions)
    assert "actor_control_frames" in executions[0]["payload"]
    assert "presentation_plan" in executions[0]["payload"]


def test_websocket_targeted_auditory_fact_event_emits_character_agent_execution_for_char_b() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "raw_fact_event",
                "payload": {
                    "event_type": "raw_fact_event",
                    "fact_family": "auditory_fact",
                    "fact_type": "speaker_active",
                    "relation_type": "speech_mode_changed",
                    "producer_ts": 902,
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {
                        "layer": "L1",
                        "system": "godot.raw_fact_emitter",
                        "actor_id": "char_a",
                        "object_id": "",
                        "environment_id": "",
                    },
                    "targets": {
                        "actor_id": "char_b",
                        "object_id": "",
                        "environment_id": "",
                    },
                    "world": {},
                    "observability": {"visual": False, "auditory": True, "occluded": False},
                    "acoustics": {
                        "loudness_band": "medium",
                        "speech_mode": "normal",
                        "reachability": "clear",
                        "ambient_noise": "quiet",
                    },
                    "effect_kind": "pulse",
                    "subject_key": "",
                    "causation_id": "aud:902",
                    "correlation_id": "aud:902",
                },
            }
        )

        received = [websocket.receive_json() for _ in range(2)]

    outputs = [message for message in received if message["message_type"] == "character_agent_output"]
    executions = [message for message in received if message["message_type"] == "character_agent_execution"]

    assert outputs == []
    assert executions
    assert executions[0]["payload"]["actor_id"] == "char_b"
    assert "actor_control_frames" in executions[0]["payload"]
    assert "presentation_plan" in executions[0]["payload"]
