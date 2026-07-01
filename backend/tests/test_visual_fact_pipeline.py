from pathlib import Path

from fastapi.testclient import TestClient
import app.main as main

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.main import (
    _handle_envelope,
    app,
    character_perceived_input_service,
    reset_runtime_state,
)
from app.debug_stream import debug_stream
from app.models.authority_event import AuthorityEvent
from app.models.player_input import FocusTargetChange
from app.models.raw_fact import RawFactEvent
from app.models.runtime_state import CharacterRuntimeStateSnapshot
from app.models.visual_fact import VisualFactEvent
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.character_runtime_state_service import CharacterRuntimeStateService
from app.services.conversation_relation_service import ConversationRelationService
from app.ws_protocol import Envelope


class _LocalGateway:
    def __init__(self) -> None:
        self._gateway = CharacterModelGateway()

    def run_task(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.run_task(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )

    def prepare_run_request(
        self,
        *,
        task_kind: str,
        context: dict[str, object],
        route_override: str | None = None,
    ) -> dict[str, object]:
        return self._gateway.prepare_run_request(
            task_kind=task_kind,
            context=context,
            route_override=route_override or "local_only",
        )


def _reset_runtime_state_with_local_character_model() -> None:
    reset_runtime_state()
    runtime = CharacterAgentRuntime()
    local_gateway = _LocalGateway()
    runtime._l2 = CharacterAgentL2Service(gateway=local_gateway, profile_registry=runtime._profile_registry)
    runtime._l3 = CharacterAgentL3Service(gateway=local_gateway)
    main.character_agent_runtime = runtime
    main.siming_event_pipeline._character_dispatch_adapter._runtime = runtime


def test_visual_fact_event_shape() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=123,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )
    assert event.fact_type == "fixed_gaze_on_target"
    assert event.target_actor_id == "char_a"


def test_visual_fact_event_model_dump_supports_environment_state_subject_key() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=900,
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        target_environment_id="env_lamp",
        effect_kind="set",
        subject_key="environment_state/env_lamp",
    )

    payload = event.model_dump()

    assert payload["effect_kind"] == "set"
    assert payload["subject_key"] == "environment_state/env_lamp"


def test_fact_reveal_bridge_does_not_degrade_into_role_conclusion_payload() -> None:
    _reset_runtime_state_with_local_character_model()
    event = AuthorityEvent.model_validate(
        {
            "event_id": "siming:fact_reveal:702:cause:1",
            "event_type": "siming.fact_reveal",
            "producer_ts": 702,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["char_b"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {
                "message_id": "msg:702",
                "presentation_hint": "surface established fact",
                "target_environment_id": "env_lamp",
            },
        }
    )
    adapter = main.FrontendSimingCharacterDispatchAdapter(runtime=main.character_agent_runtime)
    result = adapter.dispatch(event)

    delivery = result.delivery_inputs[0]
    delivery_payload = delivery.model_dump(exclude_none=True)
    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    event_types = [entry["event_type"] for entry in timeline]

    assert delivery.band == "fact_reveal"
    assert delivery.input_type == "siming_high_level_message"
    assert delivery_payload["target_actor_id"] == "char_b"
    assert "believe_X_now" not in delivery_payload
    assert "choose_Y_now" not in delivery_payload
    assert "go_to_position" not in delivery_payload
    assert "siming_output_event" in event_types
    assert "l2_reasoning_request" in event_types
    assert "character_interpretation_event" in event_types
    assert "character_agent_execution_request" in event_types
    assert "relational_belief_event" not in event_types


def test_relation_service_projects_environment_visual_fact_to_runtime_state() -> None:
    service = ConversationRelationService()
    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=150,
            fact_type="light_level_drop",
            relation_type="environment_light_drop",
            target_environment_id="env_lamp",
        )
    )

    projection = service.project_runtime_state("char_c")

    assert projection is not None
    assert projection["current_attention_source"] == "visual_fact"
    assert projection["current_focus_target"] == "env_lamp"
    assert projection["nearby_environment_refs"] == ["env_lamp"]


def test_websocket_environment_visual_fact_emits_runtime_delta_without_candidate() -> None:
    _reset_runtime_state_with_local_character_model()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "visual_fact_event",
                "payload": {
                    "actor_id": "char_c",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "producer_ts": 151,
                    "fact_type": "light_level_drop",
                    "relation_type": "environment_light_drop",
                    "target_environment_id": "env_lamp",
                },
            }
        )
        ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        remaining = [websocket.receive_json() for _ in range(5)]

    direct_siming_output = next(
        message
        for message in remaining
        if message["message_type"] == "siming_output"
        and message["payload"].get("target_actor_id") == "char_b"
    )
    candidate_event = next(
        message for message in remaining if message["message_type"] == "conversation_candidate_event"
    )
    candidate_runtime_delta = next(
        message
        for message in remaining
        if message["message_type"] == "character_runtime_state_delta"
        and message["payload"].get("conversation_candidate_refs") == ["cand_env_lamp"]
    )
    siming_output = next(
        message
        for message in remaining
        if message["message_type"] == "siming_output"
        and message["payload"].get("target_actor_id") is None
    )
    suggestion_packet = next(
        message for message in remaining if message["message_type"] == "character_agent_suggestion"
    )

    assert ack["message_type"] == "ack"
    assert ack["payload"]["route"] == "authority_visual_fact"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["current_attention_source"] == "visual_fact"
    assert runtime_delta["payload"]["current_focus_target"] == "env_lamp"
    assert runtime_delta["payload"]["nearby_environment_refs"] == ["env_lamp"]
    assert direct_siming_output["message_type"] == "siming_output"
    assert direct_siming_output["payload"]["target_environment_id"] == "env_lamp"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_object_ids"] == []
    assert candidate_event["payload"]["candidate_environment_ids"] == ["env_lamp"]
    assert candidate_runtime_delta["message_type"] == "character_runtime_state_delta"
    assert candidate_runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_env_lamp"]
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_actor_id"] is None
    assert siming_output["payload"]["target_environment_id"] == "env_lamp"
    assert suggestion_packet["message_type"] == "character_agent_suggestion"
    assert suggestion_packet["payload"]["actor_id"] == "char_c"
    assert suggestion_packet["payload"]["control_mode"] == "player_priority_assisted"


def test_handle_envelope_raw_visual_fact_matches_legacy_visual_fact_runtime_messages() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=152,
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        target_environment_id="env_lamp",
    )

    _reset_runtime_state_with_local_character_model()
    legacy_messages = _handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=event.to_legacy_payload(),
        )
    )

    _reset_runtime_state_with_local_character_model()
    raw_messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    assert legacy_messages[0]["message_type"] == "ack"
    assert raw_messages[0]["message_type"] == "ack"
    assert legacy_messages[0]["payload"]["accepted"] is True
    assert raw_messages[0]["payload"]["accepted"] is True
    assert legacy_messages[0]["payload"]["route"] == "authority_visual_fact"
    assert raw_messages[0]["payload"]["route"] == "authority_visual_fact"
    assert legacy_messages[1:] == raw_messages[1:]


def test_handle_envelope_raw_visual_fact_still_routes_after_candidate_compilation_integration() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=400,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    _reset_runtime_state_with_local_character_model()
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "authority_visual_fact"


def test_raw_visual_fact_updates_character_perceived_input_path() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=601,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    _reset_runtime_state_with_local_character_model()
    _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    perceived = character_perceived_input_service.get_latest("char_a")

    assert perceived is not None
    assert perceived.actor_id == "char_a"
    assert perceived.percept_channel == "visual"
    assert perceived.clarity_score == 1.0
    assert perceived.certainty_score == 1.0


def test_raw_visual_fact_for_char_a_emits_character_agent_execution() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=602,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    _reset_runtime_state_with_local_character_model()
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    output_messages = [message for message in messages if message["message_type"] == "character_agent_output"]
    execution_messages = [message for message in messages if message["message_type"] == "character_agent_execution"]

    assert output_messages == []
    assert execution_messages
    assert execution_messages[0]["payload"]["actor_id"] == "char_a"
    assert "actor_control_frames" in execution_messages[0]["payload"]
    assert "presentation_plan" in execution_messages[0]["payload"]


def test_raw_thermal_fact_for_char_a_emits_character_agent_execution() -> None:
    _reset_runtime_state_with_local_character_model()
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload={
                "event_type": "raw_fact_event",
                "fact_family": "thermal_fact",
                "fact_type": "thermal_proximity_changed",
                "relation_type": "thermal_proximity_changed",
                "producer_ts": 603,
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
                    "object_id": "obj_letter",
                    "environment_id": "",
                },
                "world": {},
                "observability": {"visual": False, "auditory": False, "occluded": False},
                "acoustics": {},
                "effect_kind": "pulse",
                "subject_key": "",
                "causation_id": "therm:603",
                "correlation_id": "therm:603",
            },
        )
    )

    execution_messages = [message for message in messages if message["message_type"] == "character_agent_execution"]
    perceived = character_perceived_input_service.get_latest("char_a")

    assert execution_messages
    assert execution_messages[0]["payload"]["actor_id"] == "char_a"
    assert perceived is not None
    assert perceived.percept_channel == "thermal"
    assert perceived.target_object_id == "obj_letter"


def test_raw_tactile_fact_for_char_a_updates_character_perceived_input_path() -> None:
    _reset_runtime_state_with_local_character_model()
    _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload={
                "event_type": "raw_fact_event",
                "fact_family": "tactile_fact",
                "fact_type": "contact_started",
                "relation_type": "contact_started",
                "producer_ts": 604,
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
                "observability": {"visual": False, "auditory": False, "occluded": False},
                "acoustics": {},
                "effect_kind": "pulse",
                "subject_key": "",
                "causation_id": "tact:604",
                "correlation_id": "tact:604",
            },
        )
    )

    perceived = character_perceived_input_service.get_latest("char_a")

    assert perceived is not None
    assert perceived.percept_channel == "tactile"


def test_interact_world_result_updates_self_body_perceived_input_path() -> None:
    _reset_runtime_state_with_local_character_model()
    _handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": "char_c",
                "intent_type": "interact_intent",
                "producer_ts": 456,
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
            },
        )
    )

    perceived = character_perceived_input_service.get_latest_self_body("char_c")

    assert perceived is not None
    assert perceived.actor_id == "char_c"
    assert perceived.body_state_class == "interaction_strain"


def test_websocket_raw_visual_fact_event_emits_same_runtime_alignment_messages_as_legacy_path() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=153,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_object",
        target_object_id="obj_letter",
    )

    _reset_runtime_state_with_local_character_model()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "raw_fact_event",
                "payload": event.model_dump(),
            }
        )
        ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        candidate_event = websocket.receive_json()
        candidate_runtime_delta = websocket.receive_json()
        siming_output = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "authority_visual_fact"
    assert ack["payload"]["source_type"] == "raw_fact_event"
    assert ack["payload"]["fact_key"] == "actor_looks_at_object"
    assert ack["payload"]["fact_type"] == "fixed_gaze_on_target"
    assert ack["payload"]["relation_type"] == "actor_looks_at_object"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["current_attention_source"] == "visual_fact"
    assert runtime_delta["payload"]["current_focus_target"] == "obj_letter"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_object_ids"] == ["obj_letter"]
    assert candidate_runtime_delta["message_type"] == "character_runtime_state_delta"
    assert candidate_runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_obj_letter"]
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_object_id"] == "obj_letter"


def test_relation_service_builds_candidate_for_visual_fact_actor_look() -> None:
    service = ConversationRelationService()
    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=124,
            fact_type="fixed_gaze_on_target",
            relation_type="actor_looks_at_actor",
            target_actor_id="char_a",
        )
    )

    event = service.build_candidate_event(
        actor_id="char_c",
        causation_id="visual_fact:124",
        correlation_id="visual_fact:124",
    )

    assert event is not None
    assert event.candidate_actor_ids == ["char_a"]
    assert event.candidate_object_ids == []


def test_relation_service_suppresses_mirrored_visual_fact_when_focus_matches() -> None:
    service = ConversationRelationService()
    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_actor_id="char_a",
        target_object_id="",
        producer_ts=200,
    )
    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=200,
            fact_type="fixed_gaze_on_target",
            relation_type="actor_looks_at_actor",
            target_actor_id="char_a",
        )
    )

    event = service.build_candidate_event(
        actor_id="char_c",
        causation_id="visual_fact:200",
        correlation_id="visual_fact:200",
    )

    assert event is None


def test_relation_service_builds_candidate_for_visual_fact_near_object() -> None:
    service = ConversationRelationService()
    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=201,
            fact_type="spatial_relation",
            relation_type="actor_near_object",
            target_object_id="obj_letter",
        )
    )

    event = service.build_candidate_event(
        actor_id="char_c",
        causation_id="visual_fact:201",
        correlation_id="visual_fact:201",
    )

    assert event is not None
    assert event.candidate_object_ids == ["obj_letter"]


def test_relation_service_projects_mirrored_object_visual_fact_to_focus_state() -> None:
    service = ConversationRelationService()
    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_actor_id="",
        target_object_id="obj_letter",
        producer_ts=205,
    )
    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=205,
            fact_type="fixed_gaze_on_target",
            relation_type="actor_looks_at_object",
            target_object_id="obj_letter",
        )
    )

    projection = service.project_runtime_state("char_c")

    assert projection is not None
    assert projection["current_attention_source"] == "focus_state"
    assert projection["current_focus_target"] == "obj_letter"


def test_relation_service_suppresses_duplicate_candidate_signature_within_window() -> None:
    service = ConversationRelationService()
    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=210,
            fact_type="spatial_relation",
            relation_type="actor_near_object",
            target_object_id="obj_letter",
        )
    )
    first = service.build_candidate_event(
        actor_id="char_c",
        causation_id="visual_fact:210",
        correlation_id="visual_fact:210",
    )
    assert first is not None
    assert service.should_emit_candidate(first) is True

    service.apply_world_result(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_letter",
        result_type="action_resolution_result",
        producer_ts=260,
    )
    second = service.build_candidate_event(
        actor_id="char_c",
        causation_id="world:260",
        correlation_id="world:260",
    )

    assert second is not None
    assert service.should_emit_candidate(second) is False


def test_runtime_state_service_suppresses_mirrored_visual_fact_after_focus() -> None:
    service = CharacterRuntimeStateService()
    service.get_or_create_snapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=300,
    )
    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=300,
        target_actor_id="char_a",
        target_object_id=None,
    )

    delta = service.apply_visual_fact(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=300,
        target_actor_id="char_a",
        target_object_id=None,
        relation_type="actor_looks_at_actor",
    )

    assert delta is None


def test_handle_envelope_visual_fact_mirror_after_focus_returns_ack_only() -> None:
    _reset_runtime_state_with_local_character_model()
    focus_messages = _handle_envelope(
        Envelope(
            message_type="player_input",
            payload=FocusTargetChange(
                player_id="p1",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                actor_id="char_c",
                intent_type="focus_target_change",
                producer_ts=301,
                target_actor_id="char_a",
            ).model_dump(),
        )
    )
    assert any(message["message_type"] == "conversation_candidate_event" for message in focus_messages)

    visual_messages = _handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=301,
                fact_type="fixed_gaze_on_target",
                relation_type="actor_looks_at_actor",
                target_actor_id="char_a",
            ).model_dump(),
        )
    )

    assert visual_messages[0]["message_type"] == "ack"
    assert visual_messages[0]["payload"]["route"] == "authority_visual_fact"
    assert not any(message["message_type"] == "character_agent_execution" for message in visual_messages[1:])
    assert not any(message["message_type"] == "siming_output" for message in visual_messages[1:])
    assert any(message["message_type"] == "siming_debug_snapshot" for message in visual_messages[1:])


def test_handle_envelope_raw_visual_fact_mirror_after_focus_matches_legacy_ack_only() -> None:
    _reset_runtime_state_with_local_character_model()
    focus_messages = _handle_envelope(
        Envelope(
            message_type="player_input",
            payload=FocusTargetChange(
                player_id="p1",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                actor_id="char_c",
                intent_type="focus_target_change",
                producer_ts=302,
                target_actor_id="char_a",
            ).model_dump(),
        )
    )
    assert any(message["message_type"] == "conversation_candidate_event" for message in focus_messages)

    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=302,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    legacy_messages = _handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=event.to_legacy_payload(),
        )
    )
    raw_messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    assert not any(message["message_type"] == "character_agent_execution" for message in legacy_messages[1:])
    assert not any(message["message_type"] == "character_agent_execution" for message in raw_messages[1:])
    assert legacy_messages[1:] == raw_messages[1:]
    assert legacy_messages[0]["message_type"] == "ack"
    assert legacy_messages[0]["payload"]["accepted"] is True
    assert legacy_messages[0]["payload"]["source_type"] == "visual_fact_event"
    assert legacy_messages[0]["payload"]["route"] == "authority_visual_fact"
    assert legacy_messages[0]["payload"]["fact_key"] == "actor_looks_at_actor"
    assert legacy_messages[0]["payload"]["fact_type"] == "fixed_gaze_on_target"
    assert legacy_messages[0]["payload"]["relation_type"] == "actor_looks_at_actor"

    assert raw_messages[0]["message_type"] == "ack"
    assert raw_messages[0]["payload"]["accepted"] is True
    assert raw_messages[0]["payload"]["source_type"] == "raw_fact_event"
    assert raw_messages[0]["payload"]["route"] == "authority_visual_fact"
    assert raw_messages[0]["payload"]["fact_key"] == "actor_looks_at_actor"
    assert raw_messages[0]["payload"]["fact_type"] == "fixed_gaze_on_target"
    assert raw_messages[0]["payload"]["relation_type"] == "actor_looks_at_actor"


def test_handle_envelope_unsupported_raw_fact_family_returns_negative_ack_only() -> None:
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=RawFactEvent(
                fact_family="unsupported_fact",
                fact_type="anything",
                relation_type="",
                producer_ts=400,
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                source={
                    "layer": "L1",
                    "system": "godot.raw_fact_emitter",
                    "actor_id": "char_c",
                },
                targets={},
            ).model_dump(),
        )
    )

    assert messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": False,
                "source_type": "raw_fact_event",
                "route": "unknown_raw_fact_family",
            },
        }
    ]


def test_websocket_visual_fact_event_emits_runtime_alignment_messages() -> None:
    _reset_runtime_state_with_local_character_model()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "visual_fact_event",
                "payload": {
                    "actor_id": "char_c",
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "producer_ts": 125,
                    "fact_type": "fixed_gaze_on_target",
                    "relation_type": "actor_looks_at_object",
                    "target_object_id": "obj_letter",
                },
            }
        )
        ack = websocket.receive_json()
        runtime_snapshot = websocket.receive_json()
        runtime_delta = websocket.receive_json()
        candidate_event = websocket.receive_json()
        candidate_runtime_delta = websocket.receive_json()
        siming_output = websocket.receive_json()

    assert ack["message_type"] == "ack"
    assert ack["payload"]["accepted"] is True
    assert ack["payload"]["route"] == "authority_visual_fact"
    assert runtime_snapshot["message_type"] == "character_runtime_state_snapshot"
    assert runtime_snapshot["payload"]["actor_id"] == "char_c"
    assert runtime_delta["message_type"] == "character_runtime_state_delta"
    assert runtime_delta["payload"]["current_attention_source"] == "visual_fact"
    assert runtime_delta["payload"]["current_focus_target"] == "obj_letter"
    assert candidate_event["message_type"] == "conversation_candidate_event"
    assert candidate_event["payload"]["candidate_object_ids"] == ["obj_letter"]
    assert candidate_runtime_delta["message_type"] == "character_runtime_state_delta"
    assert candidate_runtime_delta["payload"]["conversation_candidate_refs"] == ["cand_obj_letter"]
    assert siming_output["message_type"] == "siming_output"
    assert siming_output["payload"]["target_object_id"] == "obj_letter"


def test_interact_success_emits_visual_evidence_projection_raw_fact() -> None:
    project_root = Path(__file__).resolve().parents[2]
    controller_source = (project_root / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "evidence_projection_emitter" in controller_source
    assert 'result_type == "object_state_result"' in controller_source
    assert 'str(payload.get("target_object_id", "")) == "obj_letter"' in controller_source
    assert 'str(payload.get("current_state", "")) == "visible"' in controller_source
    assert 'emit_visual_evidence_projection("obj_letter")' in controller_source


def test_raw_fact_event_debug_trace_exposes_l1_to_l2_transition_order_without_replacing_authority_ack() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=999,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    _reset_runtime_state_with_local_character_model()
    debug_stream.clear()
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "authority_visual_fact"

    stages = [entry["stage"] for entry in debug_stream.history()]

    assert "l1_raw_fact_ingress" in stages
    assert "candidate_percept_compiled" in stages
    assert "character_perceived_applied" in stages
    assert stages.index("l1_raw_fact_ingress") < stages.index("candidate_percept_compiled")
    assert stages.index("candidate_percept_compiled") < stages.index("character_perceived_applied")


def test_actor_local_sampling_emits_standard_visual_fact_shape() -> None:
    text = (Path(__file__).resolve().parents[2] / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "emit_fixed_gaze_on_target" in text
    assert 'message_type": "visual_fact_event"' not in text


def test_social_spatial_settlement_result_is_projected_back_into_runtime_outputs() -> None:
    event = AuthorityEvent.model_validate(
        {
            "event_id": "esm_result:approach:1",
            "event_type": "esm_result_event",
            "producer_ts": 901,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "esm", "actor_id": "char_a"},
            "routing": {
                "audience_mode": "room",
                "routing_mode": "event_type",
                "target_ids": ["presentation"],
            },
            "priority": "p1",
            "ttl": None,
            "durability": "replayable",
            "causation_id": "character_agent:0:char_a",
            "correlation_id": "character_agent:0:char_a",
            "payload": {
                "result_id": "action_resolution:character_agent:0:char_a:approach",
                "result_type": "action_resolution_result",
                "actor_id": "char_a",
                "target_actor_id": "char_b",
                "action_profile": "approach",
                "settlement_status": "accepted",
                "producer_ts": 1,
            },
        }
    )

    projector = main.FrontendAuthorityEventProjector()
    projector.handle_event(event)
    projected = projector.drain()

    social_spatial_results = [
        message for message in projected if message["message_type"] == "social_spatial_runtime_result"
    ]

    assert social_spatial_results
    assert social_spatial_results[0]["payload"]["actor_id"] == "char_a"
    assert social_spatial_results[0]["payload"]["target_actor_id"] == "char_b"
    assert social_spatial_results[0]["payload"]["action_profile"] == "approach"
