import pytest
from pydantic import ValidationError

from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    InterventionDecision,
)


def test_intervention_candidate_accepts_only_candidate_level_fields() -> None:
    candidate = InterventionCandidate(
        candidate_id="cand:light:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        target_environment_id="env_lamp",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        explanation="Make the established light drop easier for char_b to notice.",
        confidence=0.74,
        reason_tags=["established_fact", "visibility"],
        source="llm",
    )

    assert candidate.proposed_band == "fact_reveal"
    assert candidate.established_fact_ids == ["visual_fact:300:char_c:light_level_drop"]
    assert candidate.confidence == 0.74


def test_intervention_candidate_rejects_forbidden_llm_control_fields() -> None:
    with pytest.raises(ValidationError, match="forbidden Siming candidate field"):
        InterventionCandidate.model_validate(
            {
                "candidate_id": "cand:bad",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "causation_id": "visual_fact:300",
                "correlation_id": "visual_fact:300",
                "proposed_band": "fact_reveal",
                "established_fact_ids": ["visual_fact:300"],
                "source": "llm",
                "authority_event": {"event_type": "siming.fact_reveal"},
            }
        )


def test_fairness_snapshot_is_structured_context_without_raw_godot_state() -> None:
    snapshot = FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
    )

    assert snapshot.known_fact_ids == ["visual_fact:300:char_c:light_level_drop"]
    assert not hasattr(snapshot, "raw_godot_state")


def test_intervention_decision_records_policy_and_feasibility_without_being_provider_output() -> None:
    decision = InterventionDecision(
        decision_id="decision:cand:light:1",
        candidate_id="cand:light:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        accepted=True,
        policy_reasons=["established_fact_visible"],
        feasibility_reasons=["visual_fact_path_available"],
    )

    assert decision.accepted is True
    assert decision.selected_path == "visual_fact_path"
