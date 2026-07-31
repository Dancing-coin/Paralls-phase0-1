import pytest
from pydantic import ValidationError

from app.character_agent.execution.kimodo_adapter_contract import KimodoActionRequest, KimodoRealizationPlan
from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.skills.models import (
    ActionSettlementResult,
    PrimitiveActionPlan,
    SkillEvaluationResult,
)
from app.models.character_agent_runtime import CharacterIntentDecision, CharacterInterpretation


def _execution_inputs() -> tuple[CharacterPrivateWorldSnapshot, CharacterInterpretation, CharacterIntentDecision]:
    return (
        CharacterPrivateWorldSnapshot(
            actor_id="char_a",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=10,
            updated_at=10,
            attention_targets=["obj_archive"],
        ),
        CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="inspect the archive",
            interpretation_type="visual_fact",
            salience_score=0.9,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="medium",
            attention_target="obj_archive",
            inner_prompt_candidate="inspect archive",
        ),
        CharacterIntentDecision(
            actor_id="char_a",
            selected_intent="inspect_object",
            persona_passed=True,
            logic_passed=True,
            gain_loss_passed=True,
            rationale="inspect archive",
        ),
    )


def test_skill_path_and_settlement_are_exposed_as_presentation_only_metadata() -> None:
    snapshot, interpretation, decision = _execution_inputs()
    executor = CharacterAgentL4Executor()
    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )
    evaluation = SkillEvaluationResult(
        actor_id="char_a",
        action_id="survey_scene",
        selected_path={"binding_id": "observation_to_survey_scene", "skill_id": "observation"},
    )
    primitive_plan = PrimitiveActionPlan(
        composite_action_id="survey_scene",
        skill_path_id="observation_to_survey_scene",
        primitive_actions=["orient_to_space", "scan_visible_changes"],
        realization_keys=["look_at_target"],
    )
    settlement = ActionSettlementResult(
        outcome_band="success_with_cost",
        costs=["time_pressure"],
        realization_hints=["focused_scan"],
    )

    executor.attach_skill_realization_metadata(
        plan=plan,
        skill_evaluation_result=evaluation,
        primitive_action_plan=primitive_plan,
        action_settlement_result=settlement,
    )
    metadata = CharacterAgentL4Adapter().realization_metadata_from_execution_plan(
        plan,
        action_settlement_result=settlement,
    )

    assert plan["action_request_bundle"]
    assert metadata == {
        "selected_skill_path": {"binding_id": "observation_to_survey_scene", "skill_id": "observation"},
        "primitive_action_tags": ["orient_to_space", "scan_visible_changes"],
        "primitive_realization_keys": ["look_at_target"],
        "settlement_outcome": {
            "outcome_band": "success_with_cost",
            "failure_domains": [],
            "primary_failure_domain": "none",
            "realization_hints": ["focused_scan"],
        },
    }

    request = KimodoActionRequest(
        actor_id="char_a",
        semantic_keys=["look_at_target"],
        execution_mode="skeletal_animation",
        realization_metadata=metadata,
    )
    realization_plan = KimodoRealizationPlan(
        actor_id="char_a",
        semantic_keys=["look_at_target"],
        execution_mode="skeletal_animation",
        realization_metadata=metadata,
    )

    assert request.realization_metadata == metadata
    assert realization_plan.realization_metadata == metadata


def test_kimodo_contract_rejects_world_authority_fields() -> None:
    with pytest.raises(ValidationError):
        KimodoRealizationPlan(
            actor_id="char_a",
            execution_mode="skeletal_animation",
            settlement_status="accepted",
        )
