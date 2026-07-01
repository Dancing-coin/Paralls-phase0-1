from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_l1 import CharacterAgentL1Service


def test_character_agent_l1_preserves_low_clarity_and_low_certainty_inputs() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=510,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/partial_observation",
        source_candidate_event_id="visual_fact:510:char_b",
        clarity_score=0.35,
        certainty_score=0.41,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.clarity_score == 0.35
    assert snapshot.certainty_score == 0.41


def test_character_agent_l1_routes_unknown_modalities_into_unresolved_signals() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="electromagnetic",
        producer_ts=511,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="unknown_fact/signal_bleed",
        source_candidate_event_id="unknown_fact:511:char_a",
        clarity_score=0.66,
        certainty_score=0.53,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.unresolved_signals == ["unknown_fact/signal_bleed"]
    assert snapshot.active_anomalies == ["unknown_fact/signal_bleed"]
    assert snapshot.distraction_level == "elevated"
    assert snapshot.clarity_score == 0.66
    assert snapshot.certainty_score == 0.53


def test_character_agent_l1_does_not_mark_high_confidence_unresolved_signal_as_active_anomaly() -> None:
    service = CharacterAgentL1Service()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="spatial",
        producer_ts=512,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="spatial_access_fact/actor_approached_actor",
        source_candidate_event_id="spatial_access_fact:512:char_a",
        target_actor_id="char_b",
        distance_m=2.0,
        clarity_score=0.91,
        certainty_score=0.88,
    )

    snapshot = service.apply_character_perceived_event(perceived)

    assert snapshot.unresolved_signals == ["spatial_access_fact/actor_approached_actor"]
    assert snapshot.active_anomalies == []
    assert snapshot.distraction_level == "baseline"
