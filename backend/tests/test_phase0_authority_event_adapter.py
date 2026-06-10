from app.models.player_input import InteractIntent
from app.models.visual_fact import VisualFactEvent
from app.models.world_result import ActionResolutionResult, ConstraintStateResult
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter


def test_adapter_converts_visual_fact_to_authority_event() -> None:
    adapter = Phase0AuthorityEventAdapter()
    event = adapter.visual_fact_event(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=300,
            fact_type="light_level_drop",
            relation_type="environment_light_drop",
            target_environment_id="env_lamp",
        )
    )

    assert event.event_type == "visual_fact_event"
    assert event.source.layer == "L1"
    assert event.source.system == "visual_fact"
    assert event.payload["established_fact_id"] == event.event_id


def test_adapter_converts_success_world_result_to_esm_result_event() -> None:
    adapter = Phase0AuthorityEventAdapter()
    source = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=456,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = ActionResolutionResult(
        request_ref="interact:456:obj_letter",
        result_id="action_resolution:interact:456:obj_letter",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        source_type="player",
        result_type="action_resolution_result",
        causation_id="interact:456",
        correlation_id="interact:456",
        producer_ts=457,
        target_object_id="obj_letter",
        resolution_status="accepted",
        resolved_entities=["obj_letter"],
        applied_state_changes=["object_state_result"],
        stable_state_summary="interaction accepted",
        settlement_status="accepted",
    )

    event = adapter.world_result_event(result, source_event=source)

    assert event.event_type == "esm_result_event"
    assert event.source.system == "esm"
    assert event.causation_id == "interact:456"
    assert event.correlation_id == "interact:456"
    assert event.payload["result_type"] == "action_resolution_result"
    assert event.payload["settlement_status"] == "accepted"


def test_adapter_converts_constraint_result_to_constraint_state_event() -> None:
    adapter = Phase0AuthorityEventAdapter()
    source = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=456,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = ConstraintStateResult(
        room_id="room_demo",
        source_type="player",
        result_type="constraint_state_result",
        causation_id="interact:456",
        producer_ts=457,
        target_object_id="obj_letter",
        constraint_type="distance",
        constraint_summary="target is too far away",
    )

    event = adapter.world_result_event(result, source_event=source)

    assert event.event_type == "constraint_state_event"
    assert event.payload["constraint_type"] == "distance"
