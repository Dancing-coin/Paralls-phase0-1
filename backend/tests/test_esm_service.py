from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def test_esm_service_accepts_nearby_interaction() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=10,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, is_in_range=True)
    assert result.result_type == "object_interaction_result"


def test_esm_service_rejects_out_of_range_interaction() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=11,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, is_in_range=False)
    assert result.result_type == "constraint_state_result"
    assert result.constraint_type == "distance"


def test_esm_service_computes_range_from_actor_position() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    near = service.resolve_interaction(event, actor_position=(0.0, 1.0, -0.5))
    far = service.resolve_interaction(event, actor_position=(0.0, 1.0, 20.0))

    assert near.result_type == "object_interaction_result"
    assert far.result_type == "constraint_state_result"


def test_esm_service_rejects_far_actor_position() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=12,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = service.resolve_interaction(event, actor_position=(0.0, 0.0, 16.0))
    assert result.result_type == "constraint_state_result"
    assert result.constraint_type == "distance"


def test_esm_service_success_result_exposes_stable_phase1_contract_fields() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=20,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    result = service.resolve_interaction(event, is_in_range=True)

    assert result.result_type == "object_interaction_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.causation_id == "interact:20"
    assert result.correlation_id == "interact:20"
    assert result.settlement_status == "accepted"


def test_esm_service_constraint_result_exposes_stable_phase1_contract_fields() -> None:
    service = ESMService()
    event = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=21,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )

    result = service.resolve_interaction(event, is_in_range=False)

    assert result.result_type == "constraint_state_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.causation_id == "interact:21"
    assert result.correlation_id == "interact:21"
    assert result.constraint_type == "distance"
    assert result.settlement_status == "rejected"


def test_esm_service_environment_shift_result_is_replayable_and_updates_field_state() -> None:
    service = ESMService()

    result = service.emit_environment_shift(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id="char_c",
        target_environment_id="env_lamp",
        previous_state="stable",
        current_state="alerted",
    )

    assert result.result_type == "environment_state_result"
    assert result.actor_id == "char_c"
    assert result.scene_id == "scene_demo"
    assert result.zone_id == "zone_focus"
    assert result.causation_id == "env:env_lamp:alerted"
    assert result.correlation_id == "env:env_lamp:alerted"
    assert result.settlement_status == "applied"
    assert result.light_level == "low"
    assert result.noise_level == "elevated"

    field = service.get_environment_field("room_demo", "zone_focus")
    assert field.light_level == "low"
    assert field.noise_level == "elevated"
