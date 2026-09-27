from app.services.conversation_relation_service import ConversationRelationService
from app.models.visual_fact import VisualFactEvent


def test_relation_service_builds_candidate_for_char_c_looking_at_char_a() -> None:
    service = ConversationRelationService()

    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_actor_id="char_a",
        target_object_id="",
        producer_ts=100,
    )

    event = service.build_candidate_event(actor_id="char_c", causation_id="focus:100", correlation_id="focus:100")

    assert event is not None
    assert event.actor_id == "char_c"
    assert event.candidate_actor_ids == ["char_a"]
    assert event.engagement_pressure == "elevated"


def test_relation_service_builds_candidate_for_char_c_near_object() -> None:
    service = ConversationRelationService()

    service.apply_world_result(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_letter",
        result_type="action_resolution_result",
        producer_ts=101,
    )

    event = service.build_candidate_event(actor_id="char_c", causation_id="world:101", correlation_id="world:101")

    assert event is not None
    assert event.candidate_object_ids == ["obj_letter"]


def test_relation_service_exposes_unified_relation_snapshot() -> None:
    service = ConversationRelationService()
    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_actor_id="char_a",
        target_object_id="",
        producer_ts=100,
    )
    snapshot = service.get_relation_snapshot("char_c")

    assert snapshot is not None
    assert snapshot["room_id"] == "room_demo"
    assert snapshot["focus_target_actor_id"] == "char_a"
    assert snapshot["focus_producer_ts"] == "100"


def test_relation_service_does_not_carry_focus_state_into_a_new_runtime_context() -> None:
    service = ConversationRelationService()
    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_previous",
        scene_id="scene_previous",
        zone_id="zone_previous",
        target_actor_id="char_a",
        target_object_id="",
        producer_ts=22_000_000,
    )

    service.apply_visual_fact(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_current",
            scene_id="scene_current",
            zone_id="zone_current",
            producer_ts=1_096,
            fact_type="fixed_gaze_on_target",
            relation_type="actor_looks_at_object",
            target_object_id="obj_letter",
        )
    )

    projection = service.project_runtime_state("char_c")

    assert projection is not None
    assert projection["room_id"] == "room_current"
    assert projection["current_attention_source"] == "visual_fact"
    assert projection["current_focus_target"] == "obj_letter"
