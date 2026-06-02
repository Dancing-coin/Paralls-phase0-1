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
