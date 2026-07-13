import pytest
from pydantic import ValidationError

from app.character_agent.execution.kimodo_adapter_contract import (
    KimodoActionRequest,
    KimodoRealizationPlan,
)
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.models.character_agent_runtime import (
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPrivateWorldSnapshot,
)


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=2100,
        updated_at=2100,
        attention_targets=["char_b"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_a",
        interpreted_summary="char_b may need a careful reply",
        interpretation_type="social_signal",
        salience_score=0.82,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_b",
        inner_prompt_candidate="answer with measured confidence",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_a",
        selected_intent="share_info",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="char_b may need a careful reply",
    )


def test_l4_adapter_threads_skill_path_and_settlement_outcome_into_realization_hints() -> None:
    executor = CharacterAgentL4Executor()
    adapter = CharacterAgentL4Adapter(executor=executor)
    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=_decision(),
    )
    plan["skill_evaluation_result"] = {
        "actor_id": "char_a",
        "action_id": "share_info",
        "selected_path": {
            "binding_id": "mediation_to_share_info",
            "skill_id": "mediation",
            "action_id": "share_info",
            "skill_path_tags": ["social", "deescalation"],
        },
        "viable_paths": [],
        "blocked_paths": [],
        "recommendation_reason": ["matches social strategy"],
        "learning_policy_snapshot": {"promotion_enabled": False},
    }
    plan["primitive_action_plan"] = {
        "composite_action_id": "share_info",
        "skill_path_id": "mediation_to_share_info",
        "primitive_actions": ["orient", "steady_voice", "offer_context"],
        "realization_keys": ["steady_voice", "open_palms"],
    }
    plan["action_settlement_result"] = {
        "outcome_band": "success_with_cost",
        "failure_domains": ["social_resistance"],
        "primary_failure_domain": "social_resistance",
        "realization_hints": ["steady_voice", "careful_distance"],
    }
    original_actions = plan["action_request_bundle"]["requested_actions"][:]

    commands = adapter.build_commands_from_execution_plan(plan)

    realization_hints = commands[0].execution_payload["presentation_plan"]["realization_hints"]
    assert realization_hints["selected_skill_path"] == {
        "binding_id": "mediation_to_share_info",
        "skill_id": "mediation",
        "action_id": "share_info",
        "skill_path_tags": ["social", "deescalation"],
    }
    assert realization_hints["primitive_action_tags"] == ["orient", "steady_voice", "offer_context"]
    assert realization_hints["settlement_outcome"] == {
        "outcome_band": "success_with_cost",
        "failure_domains": ["social_resistance"],
        "primary_failure_domain": "social_resistance",
        "realization_hints": ["steady_voice", "careful_distance"],
    }
    assert commands[0].execution_payload["action_request_bundle"]["requested_actions"] == original_actions


def test_kimodo_contracts_accept_realization_hints_without_authority_fields() -> None:
    request = KimodoActionRequest(
        actor_id="char_a",
        semantic_keys=["share_info", "steady_voice"],
        target_actor_id="char_b",
        execution_mode="skeletal_animation",
        selected_skill_path={
            "binding_id": "mediation_to_share_info",
            "skill_id": "mediation",
            "skill_path_tags": ["social"],
        },
        primitive_action_tags=["orient", "steady_voice"],
        settlement_outcome={
            "outcome_band": "partial",
            "failure_domains": ["social_resistance"],
        },
    )
    plan = KimodoRealizationPlan(
        actor_id="char_a",
        semantic_keys=["share_info", "steady_voice"],
        execution_mode="skeletal_animation",
        selected_skill_path={
            "binding_id": "mediation_to_share_info",
            "skill_id": "mediation",
            "skill_path_tags": ["social"],
        },
        primitive_action_tags=["orient", "steady_voice"],
        settlement_outcome={
            "outcome_band": "partial",
            "failure_domains": ["social_resistance"],
        },
    )

    assert request.selected_skill_path.binding_id == "mediation_to_share_info"
    assert request.primitive_action_tags == ["orient", "steady_voice"]
    assert plan.settlement_outcome.outcome_band == "partial"

    with pytest.raises(ValidationError):
        KimodoActionRequest(
            actor_id="char_a",
            semantic_keys=["share_info"],
            execution_mode="skeletal_animation",
            settlement_success=True,
        )

    with pytest.raises(ValidationError):
        KimodoActionRequest(
            actor_id="char_a",
            semantic_keys=["share_info"],
            execution_mode="skeletal_animation",
            settlement_outcome={"settlement_success": True},
        )

    with pytest.raises(ValidationError):
        KimodoRealizationPlan(
            actor_id="char_a",
            semantic_keys=["share_info"],
            execution_mode="skeletal_animation",
            world_state_patch={"lamp": "on"},
        )

    with pytest.raises(ValidationError):
        KimodoRealizationPlan(
            actor_id="char_a",
            semantic_keys=["share_info"],
            execution_mode="skeletal_animation",
            settlement_outcome={"world_state_patch": {"lamp": "on"}},
        )
