from app.models.siming_event import InterventionCandidate
from app.services.siming_feasibility import SimingExecutionFeasibility


def make_candidate(**overrides: object) -> InterventionCandidate:
    payload = {
        "candidate_id": "cand:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


def test_visual_fact_candidate_maps_to_visual_fact_path() -> None:
    result = SimingExecutionFeasibility().evaluate(
        make_candidate(target_environment_id="env_lamp")
    )

    assert result.accepted is True
    assert result.selected_path == "visual_fact_path"
    assert "visual_fact_path_available" in result.reasons


def test_character_candidate_maps_to_character_input_path() -> None:
    result = SimingExecutionFeasibility().evaluate(make_candidate(target_environment_id=None))

    assert result.accepted is True
    assert result.selected_path == "character_input_path"


def test_environment_request_candidate_requires_environment_target() -> None:
    result = SimingExecutionFeasibility().evaluate(
        make_candidate(proposed_band="environment_request", target_environment_id=None)
    )

    assert result.accepted is False
    assert result.selected_path == "no_action"
    assert "missing_environment_target" in result.reasons


def test_environment_request_maps_to_environment_change_path_without_claiming_success() -> None:
    result = SimingExecutionFeasibility().evaluate(
        make_candidate(
            proposed_band="environment_request",
            target_environment_id="env_lamp",
            reason_tags=["esm_validated_request"],
        )
    )

    assert result.accepted is True
    assert result.selected_path == "environment_change_path"
    assert "esm_result_required_for_success" in result.reasons
