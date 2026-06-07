from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_perceived_input_service import CharacterPerceivedInputService


def test_character_perceived_input_service_stores_latest_event_per_actor() -> None:
    service = CharacterPerceivedInputService()

    event = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=700,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:700:char_a",
    )

    payload = service.apply_character_perceived_event(event)

    assert payload["actor_id"] == "char_a"
    assert service.get_latest("char_a") == event
