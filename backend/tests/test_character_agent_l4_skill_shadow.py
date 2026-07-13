from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_demo",
        producer_ts=10,
        visible_entities=[],
        audible_entities=[],
        attention_targets=["char_b"],
        updated_at=10,
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="char_b is injured and anxious",
        interpretation_type="social_signal",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="medium",
        opportunity_level="medium",
        attention_target="char_b",
        inner_prompt_candidate="help char_b",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="share_info",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="offer help",
    )


def test_l4_execution_plan_includes_composite_action_proposal_without_changing_existing_bundle() -> None:
    plan = CharacterAgentL4Executor().build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )

    proposal = plan["composite_action_proposal"]

    assert proposal["actor_id"] == "char_a"
    assert proposal["source_intent"] == "share_info"
    assert proposal["action_id"] == "share_info"
    assert proposal["target_refs"] == {"actor": "char_b"}
    assert "action_request_bundle" in plan
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "share_info"
    assert "skill_evaluation_result" not in plan
    assert "primitive_action_plan" not in plan
