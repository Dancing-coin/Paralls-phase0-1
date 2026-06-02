from app.models.runtime_state import ConversationCandidateEvent
from app.models.visual_fact import VisualFactEvent
from app.services.siming_service import SimingService


def test_siming_emits_attention_prompt_when_object_changes() -> None:
    service = SimingService()
    result = service.evaluate_world_event(
        room_id="room_demo",
        actor_id="char_b",
        object_id="obj_letter",
        event_type="object_removed_from_surface",
    )
    assert result.output_type == "attention_prompt"
    assert result.target_actor_id == "char_b"


def test_siming_emits_attention_prompt_for_char_c_candidate_actor() -> None:
    service = SimingService()
    event = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=200,
        candidate_actor_ids=["char_a"],
        candidate_object_ids=[],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        causation_id="cand:200",
        correlation_id="cand:200",
    )

    result = service.evaluate_candidate_relationship(event)

    assert result.output_type == "attention_prompt"
    assert result.target_actor_id == "char_a"


def test_siming_emits_attention_prompt_for_light_level_drop_visual_fact() -> None:
    service = SimingService()
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=300,
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        target_environment_id="env_lamp",
    )

    result = service.evaluate_visual_fact(event)

    assert result is not None
    assert result.output_type == "attention_prompt"
    assert result.target_actor_id == "char_b"
    assert result.target_environment_id == "env_lamp"


def test_siming_emits_attention_prompt_for_candidate_environment() -> None:
    service = SimingService()
    event = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=301,
        candidate_actor_ids=[],
        candidate_object_ids=[],
        candidate_environment_ids=["env_lamp"],
        engagement_pressure="present",
        privacy_risk_hint="low",
        causation_id="visual_fact:301",
        correlation_id="visual_fact:301",
    )

    result = service.evaluate_candidate_relationship(event)

    assert result.output_type == "attention_prompt"
    assert result.target_environment_id == "env_lamp"
