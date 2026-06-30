from app.character_agent.models.goal_runtime import CharacterGoalHint
from app.character_agent.reasoning.cognition_engine import CharacterCognitionEngine


def test_cognition_engine_builds_social_probe_update_with_typed_goal_hints() -> None:
    engine = CharacterCognitionEngine()

    update = engine.build_update(
        actor_id="char_a",
        summary="auditory_fact/speaker_active",
        interpretation_type="social_signal",
        salience_score=0.82,
        ambiguity_level="medium",
        risk_level="medium",
        opportunity_level="low",
        attention_target="char_b",
        snapshot={
            "clarity_score": 0.82,
            "certainty_score": 0.61,
        },
        event={
            "actor_id": "char_a",
            "percept_channel": "auditory",
            "perceived_summary": "auditory_fact/speaker_active",
            "target_actor_id": "char_b",
            "clarity_score": 0.82,
            "certainty_score": 0.61,
        },
        memory={
            "knowledge_memories": [
                {
                    "proposition_key": "char_b:is_hiding_something",
                    "proposition": "char_b may be hiding something",
                    "state": "suspected",
                    "confidence": 0.62,
                }
            ],
            "social_memories": [{"entity_id": "char_b", "trust_baseline": 0.25, "suspicion_baseline": 0.75}],
            "higher_order_memories": [
                {
                    "subject_actor_id": "char_b",
                    "proposition_key": "social_probe:knowledge_asymmetry",
                    "meta_belief": "char_b suspects char_a knows more",
                    "confidence": 0.72,
                }
            ],
            "relational_memories": [],
        },
    )

    assert update.belief_deltas[0].proposition_key == "char_b:is_probing"
    assert isinstance(update.goal_hints[0], CharacterGoalHint)
    assert "guarded_attention" in update.goal_hints[0].evidence_tags
    assert update.reasoning_trace_summary == "char_a:auditory_fact/speaker_active"


def test_cognition_engine_builds_complete_body_state_reasoning_output() -> None:
    engine = CharacterCognitionEngine()

    output = engine.build_reasoning_output(
        actor_id="char_b",
        snapshot={
            "body_state_hints": ["interaction_strain:body_state_result/interaction_strain=engaged"],
            "clarity_score": 1.0,
            "certainty_score": 1.0,
        },
        event={
            "actor_id": "char_b",
            "body_state_class": "interaction_strain",
            "perceived_summary": "body_state_result/interaction_strain=engaged",
            "clarity_score": 1.0,
            "certainty_score": 1.0,
        },
        memory={},
    )

    assert output["interpretation_type"] == "body_state"
    assert output["risk_level"] == "medium"
    assert output["belief_deltas"][0]["proposition_key"] == "self:interaction_strain"
    assert output["goal_hints"][0]["goal"] == "protect_self"


def test_cognition_engine_builds_complete_siming_reasoning_output_without_fake_belief() -> None:
    engine = CharacterCognitionEngine()

    output = engine.build_reasoning_output(
        actor_id="char_a",
        snapshot={
            "last_siming_catalyst": "watch env_lamp",
            "attention_targets": ["env_lamp"],
            "vigilance_level": "elevated",
            "clarity_score": 0.85,
            "certainty_score": 0.9,
        },
        event={
            "actor_id": "char_a",
            "percept_channel": "siming",
            "presentation_hint": "watch env_lamp",
            "pressure_hint": "crowd closing in",
            "reason_scope": "threat_scan",
            "target_environment_id": "env_lamp",
            "salience_boost": 0.85,
            "clarity_score": 0.85,
            "certainty_score": 0.9,
        },
        memory={},
    )

    assert output["attention_target"] == "env_lamp"
    assert output["belief_deltas"] == []
    assert output["dynamic_state_delta"]["vigilance_level"] >= 0.8
    assert output["goal_hints"][0]["goal"] == "protect_self" or output["goal_hints"][0]["goal"] == "preserve_optionality"
