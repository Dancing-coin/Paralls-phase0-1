import pytest

from app.character_agent.gateway.output_validator import CharacterStructuredOutputValidator


def _l3_output() -> dict[str, object]:
    return {
        "candidate_intents": ["observe", "ask_probe", "defer"],
        "selected_intent": "observe",
        "recommended_intents": ["observe", "ask_probe"],
        "risk_notes": [],
        "why_this_now": "visible change",
        "role_consistency_hint": "keep the turn bounded",
        "active_goal_frame": {"primary_goal": "keep the turn bounded"},
        "planning_horizon": 9,
        "confidence": 1.4,
    }


def test_l3_admission_gate_caps_candidates_horizon_and_confidence_without_changing_selection():
    output = CharacterStructuredOutputValidator().validate(
        task_kind="l3_planning",
        output=_l3_output(),
        cognition_policy={"max_candidate_intents": 2, "max_planning_horizon": 3, "confidence_ceiling": 0.8},
    )

    assert output["candidate_intents"] == ["observe", "ask_probe"]
    assert output["selected_intent"] == "observe"
    assert output["planning_horizon"] == 3
    assert output["confidence"] == 0.8
    assert output["gate_result"]["status"] == "accepted_with_degradation"
    assert "candidate_intents" in output["gate_result"]["capped_fields"]


def test_l3_admission_gate_rejects_selected_intent_that_is_pruned_by_policy():
    try:
        CharacterStructuredOutputValidator().validate(
            task_kind="l3_planning",
            output={**_l3_output(), "selected_intent": "defer"},
            cognition_policy={"max_candidate_intents": 2},
        )
    except ValueError as exc:
        assert "selected_intent" in str(exc)
    else:
        raise AssertionError("expected selected intent outside capped candidates to be rejected")


def test_dialogue_gate_records_unsupported_domain_as_degradation():
    output = CharacterStructuredOutputValidator().validate(
        task_kind="dialogue_generation",
        output={"content": "hello", "tone": "neutral"},
        cognition_policy={"supported_domains": ["archive"], "requested_domain": "combat"},
    )

    assert output["gate_result"]["status"] == "accepted_with_degradation"
    assert "unsupported_domain" in output["gate_result"]["reasons"]


def test_l3_gate_rejects_unknown_duplicate_or_reordered_frozen_wire_labels():
    validator = CharacterStructuredOutputValidator()
    base = {
        "selected_intent": "observe",
        "recommended_intents": ["observe"],
        "risk_notes": [],
            "why_this_now": "observe the current frame",
            "role_consistency_hint": "stay within the frame",
            "active_goal_frame": {"primary_goal": "stay within the frame"},
    }
    for labels in (["observe", "unknown"], ["observe", "observe"], ["defer", "observe"]):
        with pytest.raises(ValueError, match="candidate labels"):
            validator.validate(
                task_kind="l3_planning",
                output={**base, "candidate_intents": labels},
                expected_candidate_labels=["observe", "defer"],
                expected_candidate_digest="sha256:candidates",
            )


def test_l3_gate_preserves_frozen_digest_for_a_valid_wire_subset():
    output = CharacterStructuredOutputValidator().validate(
        task_kind="l3_planning",
        output={
            "candidate_intents": ["observe"],
            "selected_intent": "observe",
            "recommended_intents": ["observe"],
            "risk_notes": [],
            "why_this_now": "observe",
            "role_consistency_hint": "bounded",
            "active_goal_frame": {"primary_goal": "bounded"},
        },
        expected_candidate_labels=["observe", "defer"],
        expected_candidate_digest="sha256:candidates",
    )
    assert output["candidate_digest"] == "sha256:candidates"
