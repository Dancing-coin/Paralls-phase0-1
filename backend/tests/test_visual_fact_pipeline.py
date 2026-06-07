from fastapi.testclient import TestClient

from app.main import _handle_envelope, app, reset_runtime_state
from app.models.player_input import FocusTargetChange
from app.models.raw_fact import RawFactEvent
from app.models.runtime_state import CharacterRuntimeStateSnapshot
from app.models.visual_fact import VisualFactEvent
from app.services.character_runtime_state_service import CharacterRuntimeStateService
from app.services.conversation_relation_service import ConversationRelationService
from app.ws_protocol import Envelope


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
    reset_runtime_state()
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
        direct_siming_output = websocket.receive_json()
        candidate_event = websocket.receive_json()
        candidate_runtime_delta = websocket.receive_json()
        siming_output = websocket.receive_json()

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

    reset_runtime_state()
    legacy_messages = _handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=event.to_legacy_payload(),
        )
    )

    reset_runtime_state()
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

    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "authority_visual_fact"


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

    reset_runtime_state()
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
        result_type="object_interaction_result",
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
    reset_runtime_state()
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

    assert [message["message_type"] for message in visual_messages] == ["ack"]


def test_handle_envelope_raw_visual_fact_mirror_after_focus_matches_legacy_ack_only() -> None:
    reset_runtime_state()
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

    assert legacy_messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": "visual_fact_event",
                "route": "authority_visual_fact",
            },
        }
    ]
    assert raw_messages == [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": "raw_fact_event",
                "route": "authority_visual_fact",
            },
        }
    ]


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
    reset_runtime_state()
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
