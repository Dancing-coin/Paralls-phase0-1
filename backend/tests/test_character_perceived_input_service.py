from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
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
    assert payload["source_actor_id"] == ""
    assert payload["target_actor_id"] == ""
    assert payload["distance_m"] is None
    assert service.get_latest("char_a") == event


def test_character_perceived_input_service_stores_latest_self_body_event_per_actor() -> None:
    service = CharacterPerceivedInputService()

    event = SelfBodyPerceivedEvent(
        actor_id="char_c",
        body_state_class="interaction_strain",
        producer_ts=701,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_c:701",
    )

    payload = service.apply_self_body_perceived_event(event)

    assert payload["actor_id"] == "char_c"
    assert payload["body_state_class"] == "interaction_strain"
    assert service.get_latest_self_body("char_c") == event
