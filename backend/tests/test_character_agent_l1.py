from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.services.character_agent_l1 import CharacterAgentL1Service


def test_character_agent_l1_tracks_latest_private_snapshot() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/fixed_gaze_on_target",
        source_candidate_event_id="visual_fact:200:char_a",
        clarity_score=1.0,
        certainty_score=1.0,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.actor_id == "char_a"
    assert snapshot.visible_entities == ["visual_fact/fixed_gaze_on_target"]
    assert snapshot.clarity_score == 1.0
    assert snapshot.certainty_score == 1.0


def test_character_agent_l1_tracks_self_body_hint() -> None:
    service = CharacterAgentL1Service()
    event = SelfBodyPerceivedEvent(
        actor_id="char_a",
        body_state_class="interaction_strain",
        producer_ts=220,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="body_state_result/interaction_strain=engaged",
        source_body_result_id="body_result:char_a:220",
    )

    snapshot = service.apply_self_body_perceived_event(event)

    assert snapshot.body_state_hints == ["interaction_strain:body_state_result/interaction_strain=engaged"]


def test_character_agent_l1_tracks_targeted_siming_catalyst() -> None:
    service = CharacterAgentL1Service()

    snapshot = service.apply_siming_output(
        {
            "target_actor_id": "char_b",
            "target_object_id": "obj_letter",
            "presentation_hint": "watch obj_letter",
            "producer_ts": 240,
            "causation_id": "siming:240",
            "correlation_id": "siming:240",
        }
    )

    assert snapshot.actor_id == "char_b"
    assert snapshot.last_siming_catalyst == "watch obj_letter"
    assert snapshot.attention_targets == ["obj_letter"]
