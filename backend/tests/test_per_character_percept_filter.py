from app.models.character_perceived import CharacterPerceivedEvent
from app.models.candidate_percept import CandidatePerceptEvent
from app.services.per_character_percept_filter import filter_candidate_for_actor


def test_character_perceived_event_shape() -> None:
    event = CharacterPerceivedEvent(
        event_type="character_perceived_event",
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=101,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="char_c is looking at char_a",
        source_candidate_event_id="cand:101",
        clarity_score=0.85,
        certainty_score=0.65,
    )

    payload = event.model_dump()

    assert payload["event_type"] == "character_perceived_event"
    assert payload["actor_id"] == "char_a"
    assert payload["perceived_summary"] == "char_c is looking at char_a"
    assert payload["clarity_score"] == 0.85
    assert payload["certainty_score"] == 0.65


def test_filter_candidate_for_matching_actor_returns_character_perceived_event() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:300",
        correlation_id="vf:300",
    )

    perceived = filter_candidate_for_actor(candidate, actor_id="char_a")

    assert perceived is not None
    assert perceived.actor_id == "char_a"
    assert perceived.percept_channel == "visual"
    assert perceived.clarity_score == 1.0
    assert perceived.certainty_score == 1.0


def test_filter_candidate_for_non_matching_actor_returns_none() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:301",
        correlation_id="vf:301",
    )

    perceived = filter_candidate_for_actor(candidate, actor_id="char_b")

    assert perceived is None


def test_filter_drops_visual_candidate_when_actor_is_not_facing_target() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=500,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:500",
        correlation_id="vf:500",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={
            "is_facing_target": False,
            "distance_m": 2.0,
            "privacy_band": "local",
            "current_zone_id": "zone_focus",
        },
    )

    assert perceived is None


def test_filter_keeps_visual_candidate_when_actor_is_facing_target() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=501,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:501",
        correlation_id="vf:501",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={
            "is_facing_target": True,
            "distance_m": 2.0,
            "privacy_band": "local",
            "current_zone_id": "zone_focus",
        },
    )

    assert perceived is not None
    assert perceived.actor_id == "char_a"
    assert perceived.clarity_score == 1.0
    assert perceived.certainty_score == 1.0


def test_filter_returns_private_event_with_quality_scores() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=610,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:610",
        correlation_id="vf:610",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={
            "is_facing_target": True,
            "distance_m": 2.0,
            "attention_focus": "char_c",
        },
    )

    assert perceived is not None
    payload = perceived.model_dump()
    assert "clarity_score" in payload
    assert "certainty_score" in payload
    assert payload["clarity_score"] == 1.0
    assert payload["certainty_score"] == 1.0


def test_filter_reduces_certainty_for_distant_candidate() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=611,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:611",
        correlation_id="vf:611",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={
            "is_facing_target": True,
            "distance_m": 6.0,
            "attention_focus": "char_c",
        },
    )

    assert perceived is not None
    assert perceived.clarity_score == 1.0
    assert perceived.certainty_score == 0.6
