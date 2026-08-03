import pytest

from app.character_agent.gateway.output_validator import CharacterStructuredOutputValidator


def _minimal_l2_output(dynamic_state_delta: dict[str, object]) -> dict[str, object]:
    return {
        "interpreted_summary": "char_b is probing",
        "interpretation_type": "social_signal",
        "salience_score": 0.8,
        "ambiguity_level": "medium",
        "risk_level": "medium",
        "opportunity_level": "low",
        "attention_target": "char_b",
        "inner_prompt_candidate": "stay guarded",
        "belief_deltas": [],
        "social_deltas": [],
        "higher_order_deltas": [],
        "dynamic_state_delta": dynamic_state_delta,
        "goal_hints": [],
        "reasoning_trace_summary": "test fixture",
    }


def _minimal_l3_output(priority: object) -> dict[str, object]:
    return {
        "candidate_intents": ["observe"],
        "selected_intent": "observe",
        "recommended_intents": ["observe"],
        "risk_notes": [],
        "why_this_now": "stay aware",
        "role_consistency_hint": "consistent",
        "active_goal_frame": {
            "primary_goal": "protect_secret",
            "goal_portfolio": [
                {
                    "goal_id": "goal_protect_secret",
                    "goal": "protect_secret",
                    "priority": priority,
                }
            ],
        },
    }


def test_output_validator_accepts_affect_valence_dynamic_state_delta() -> None:
    validator = CharacterStructuredOutputValidator()

    normalized = validator.validate(
        task_kind="l2_reasoning",
        output=_minimal_l2_output({"affect_valence": -0.8}),
    )

    dynamic_state_delta = normalized["dynamic_state_delta"]
    assert isinstance(dynamic_state_delta, dict)
    assert dynamic_state_delta == {"affect_valence": -0.8}


def test_output_validator_accepts_positive_affect_dynamic_state_delta_fields() -> None:
    validator = CharacterStructuredOutputValidator()

    normalized = validator.validate(
        task_kind="l2_reasoning",
        output=_minimal_l2_output(
            {
                "joy": 0.7,
                "calm": 0.6,
                "trust": 0.5,
                "gratitude": 0.4,
                "pride": 0.3,
                "confidence": 0.2,
                "hope": 0.1,
            }
        ),
    )

    dynamic_state_delta = normalized["dynamic_state_delta"]
    assert isinstance(dynamic_state_delta, dict)
    assert dynamic_state_delta == {
        "joy": 0.7,
        "calm": 0.6,
        "trust": 0.5,
        "gratitude": 0.4,
        "pride": 0.3,
        "confidence": 0.2,
        "hope": 0.1,
    }


def test_output_validator_rejects_out_of_range_affect_valence_dynamic_state_delta() -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError):
        validator.validate(
            task_kind="l2_reasoning",
            output=_minimal_l2_output({"affect_valence": -1.1}),
        )


def test_output_validator_preserves_explicit_zero_goal_portfolio_priority() -> None:
    validator = CharacterStructuredOutputValidator()

    normalized = validator.validate(
        task_kind="l3_planning",
        output=_minimal_l3_output(0.0),
    )

    active_goal_frame = normalized["active_goal_frame"]
    assert isinstance(active_goal_frame, dict)
    goal_portfolio = active_goal_frame["goal_portfolio"]
    assert isinstance(goal_portfolio, list)
    assert goal_portfolio[0]["priority"] == 0.0


@pytest.mark.parametrize("priority", [True, "nan", "inf"])
def test_output_validator_rejects_bool_and_non_finite_goal_portfolio_priority(
    priority: object,
) -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError):
        validator.validate(
            task_kind="l3_planning",
            output=_minimal_l3_output(priority),
        )


@pytest.mark.parametrize("affect_valence", [True, "nan", "inf"])
def test_output_validator_rejects_bool_and_non_finite_affect_valence_dynamic_state_delta(
    affect_valence: object,
) -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError):
        validator.validate(
            task_kind="l2_reasoning",
            output=_minimal_l2_output({"affect_valence": affect_valence}),
        )


@pytest.mark.parametrize("value", [True, "nan", "inf", 1.1])
def test_output_validator_rejects_invalid_positive_affect_delta_fields(value: object) -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError):
        validator.validate(
            task_kind="l2_reasoning",
            output=_minimal_l2_output({"trust": value}),
        )


def test_output_validator_preserves_explicit_zero_numeric_delta_fields() -> None:
    validator = CharacterStructuredOutputValidator()

    normalized = validator.validate(
        task_kind="l2_reasoning",
        output={
            **_minimal_l2_output({"affect_valence": 0.0}),
            "social_deltas": [
                {
                    "entity_id": "char_b",
                    "trust_baseline": 0.0,
                }
            ],
            "goal_hints": [
                {
                    "goal": "protect_secret",
                    "strength": 0.0,
                }
            ],
        },
    )

    dynamic_state_delta = normalized["dynamic_state_delta"]
    social_deltas = normalized["social_deltas"]
    goal_hints = normalized["goal_hints"]
    assert isinstance(dynamic_state_delta, dict)
    assert isinstance(social_deltas, list)
    assert isinstance(goal_hints, list)
    assert dynamic_state_delta["affect_valence"] == 0.0
    assert social_deltas[0]["trust_baseline"] == 0.0
    assert goal_hints[0]["strength"] == 0.0


def test_output_validator_omits_none_dynamic_state_delta_fields() -> None:
    validator = CharacterStructuredOutputValidator()

    normalized = validator.validate(
        task_kind="l2_reasoning",
        output=_minimal_l2_output({"social_pressure": None}),
    )

    dynamic_state_delta = normalized["dynamic_state_delta"]
    assert isinstance(dynamic_state_delta, dict)
    assert dynamic_state_delta == {}


def test_output_validator_rejects_unknown_dynamic_state_delta_fields() -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError):
        validator.validate(
            task_kind="l2_reasoning",
            output=_minimal_l2_output({"curiosity_state": "high"}),
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"salience_score": True},
        {"salience_score": "nan"},
        {"salience_score": "inf"},
        {"belief_deltas": [{"proposition_key": "char_b:is_probing", "confidence": True}]},
        {"social_deltas": [{"entity_id": "char_b", "trust_baseline": False}]},
        {
            "higher_order_deltas": [
                {
                    "subject_actor_id": "char_b",
                    "meta_belief": "char_b is watching",
                    "confidence": True,
                }
            ]
        },
        {"goal_hints": [{"goal": "protect_secret", "strength": False}]},
    ],
)
def test_output_validator_rejects_bool_and_non_finite_shared_numeric_fields(
    payload: dict[str, object],
) -> None:
    validator = CharacterStructuredOutputValidator()

    with pytest.raises(ValueError):
        validator.validate(
            task_kind="l2_reasoning",
            output={
                **_minimal_l2_output({}),
                **payload,
            },
        )
