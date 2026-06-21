from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.models.character_agent_runtime import CharacterInterpretation, CharacterIntentDecision, CharacterPrivateWorldSnapshot


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1500,
        updated_at=1500,
        attention_targets=["char_a"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a may be speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.88,
        ambiguity_level="medium",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="listen before responding",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="speak_public",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="char_a may be speaking nearby",
    )


def test_l4_execution_plan_exposes_actor_substrate_ingress_shape() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    assert plan["actor_control_frames"]
    assert plan["presentation_plan"]
    assert "target_ref" in plan["presentation_plan"]
    assert "expression_hint" in plan["presentation_plan"]
    assert "physiology_hint" in plan["presentation_plan"]


def test_actor_substrate_ingress_target_is_not_plain_command_type_only() -> None:
    executor = CharacterAgentL4Executor()

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    assert "command_type" not in plan
    assert "actor_control_frames" in plan
    assert "presentation_plan" in plan
