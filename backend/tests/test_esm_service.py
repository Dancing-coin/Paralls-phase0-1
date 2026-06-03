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
