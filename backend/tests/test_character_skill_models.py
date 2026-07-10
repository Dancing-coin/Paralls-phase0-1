import pytest
from pydantic import ValidationError

from app.character_agent.skills.models import (
    ActionDefinition,
    CharacterSkillState,
    CompositeActionProposal,
    PrimitiveActionPlan,
    SkillActionBinding,
    SkillDefinition,
    SkillEvidence,
    SkillEvaluationResult,
    SkillLearningPolicy,
)


def test_skill_definition_tracks_settlement_domains_and_learning_policy() -> None:
    skill = SkillDefinition(
        skill_id="first_aid",
        display_name="First Aid",
        settlement_categories=["cognitive", "tool", "social"],
        domains=["medical", "emergency_response"],
        role_tags=["field_medic"],
        learnability="trained",
        risk_tags=["infection_risk"],
    )

    assert skill.skill_id == "first_aid"
    assert skill.settlement_categories == ["cognitive", "tool", "social"]
    assert skill.learnability == "trained"


def test_action_definition_supports_composite_templates_and_variants() -> None:
    action = ActionDefinition(
        action_id="stabilize_injured_actor",
        kind="composite",
        target_types=["actor"],
        settlement_categories=["cognitive", "physical", "social", "tool"],
        primitive_sequence_templates={
            "first_aid_path": [
                "approach_target",
                "kneel_near_target",
                "inspect_wound",
                "apply_pressure",
                "speak_reassurance",
            ]
        },
        variant_rules=[
            {
                "when": {"outcome_band": "clean_success"},
                "presentation_tags": ["focused_care", "steady_breath"],
                "realization_keys": ["medical_stabilize"],
            }
        ],
    )

    assert action.kind == "composite"
    assert action.primitive_sequence_templates["first_aid_path"][-1] == "speak_reassurance"
    assert action.variant_rules[0]["when"]["outcome_band"] == "clean_success"


def test_skill_action_binding_keeps_eligibility_quality_and_learning_separate() -> None:
    binding = SkillActionBinding(
        binding_id="first_aid_to_stabilize",
        skill_id="first_aid",
        action_id="stabilize_injured_actor",
        skill_path_tags=["medical", "nonviolent", "urgent_care"],
        eligibility={
            "required_rank": "basic",
            "required_world_affordances": ["target.injured"],
            "optional_tools": ["bandage", "clean_cloth"],
        },
        quality={
            "primary_weight": 0.7,
            "supporting_skills": {"triage": 0.2, "emotional_regulation": 0.1},
            "runtime_modifiers": {"stress_load": -0.15, "calm": 0.08},
        },
        learning={
            "evidence_on_attempt": True,
            "evidence_on_blocked": False,
            "evidence_channels": ["improvement", "specialization", "confidence"],
        },
    )

    assert binding.eligibility["required_rank"] == "basic"
    assert binding.quality["supporting_skills"]["triage"] == 0.2
    assert binding.learning["evidence_on_blocked"] is False


def test_character_skill_state_is_actor_specific_and_source_typed() -> None:
    state = CharacterSkillState(
        actor_id="char_a",
        skill_id="first_aid",
        source="authored",
        rank="trained",
        proficiency=0.65,
        confidence=0.7,
        familiarity={"bleeding_control": 0.4},
        visibility={"player_visible": True, "visible_to_actors": ["char_self"]},
    )

    assert state.actor_id == "char_a"
    assert state.proficiency == 0.65
    assert state.visibility["player_visible"] is True


def test_character_skill_state_rejects_out_of_range_proficiency() -> None:
    with pytest.raises(ValidationError):
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="trained",
            proficiency=1.2,
        )


def test_character_skill_state_rejects_string_numeric_values() -> None:
    with pytest.raises(ValidationError):
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="trained",
            proficiency="0.5",
        )

    with pytest.raises(ValidationError):
        CharacterSkillState(
            actor_id="char_a",
            skill_id="first_aid",
            source="authored",
            rank="trained",
            confidence="0.5",
        )


def test_evaluation_result_carries_viable_and_blocked_paths() -> None:
    result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={"binding_id": "first_aid_to_stabilize", "skill_id": "first_aid"},
        viable_paths=[
            {
                "binding_id": "first_aid_to_stabilize",
                "skill_id": "first_aid",
                "eligibility_status": "eligible",
                "objective_feasibility": 0.72,
                "character_fit": 0.84,
                "expected_quality": "success_with_cost",
                "risk_estimate": {"infection_risk": "medium"},
            }
        ],
        blocked_paths=[
            {
                "binding_id": "healing_magic_to_stabilize",
                "missing_requirements": ["healing_magic.basic"],
            }
        ],
        recommendation_reason=["matches_nonviolent_strategy"],
        learning_policy_snapshot={"promotion_enabled": False},
    )

    assert result.selected_path["skill_id"] == "first_aid"
    assert result.viable_paths[0]["expected_quality"] == "success_with_cost"
    assert result.blocked_paths[0]["missing_requirements"] == ["healing_magic.basic"]


def test_composite_action_proposal_preserves_strategy_preferences() -> None:
    proposal = CompositeActionProposal(
        proposal_id="proposal:1",
        actor_id="char_a",
        source_intent="help_injured_actor",
        action_id="stabilize_injured_actor",
        target_refs={"patient": "char_b"},
        preferred_strategy_tags=["medical", "nonviolent"],
        forbidden_strategy_tags=["aggressive_force"],
        desired_outcomes=["stabilize_patient", "avoid_panic"],
    )

    assert proposal.target_refs["patient"] == "char_b"
    assert proposal.preferred_strategy_tags == ["medical", "nonviolent"]
    assert proposal.forbidden_strategy_tags == ["aggressive_force"]


def test_skill_models_reject_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        SkillDefinition(
            skill_id="first_aid",
            display_name="First Aid",
            undocumented_runtime_hook=True,
        )


def test_primitive_action_plan_preserves_selected_skill_path() -> None:
    plan = PrimitiveActionPlan(
        composite_action_id="stabilize_injured_actor",
        skill_path_id="first_aid_to_stabilize",
        primitive_actions=[
            "approach_target",
            "kneel_near_target",
            "inspect_wound",
            "apply_pressure",
            "speak_reassurance",
        ],
        realization_keys=["approach_careful", "kneel_inspect", "apply_pressure", "calm_voice"],
    )

    assert plan.skill_path_id == "first_aid_to_stabilize"
    assert "calm_voice" in plan.realization_keys


def test_skill_learning_policy_defaults_to_no_promotion() -> None:
    policy = SkillLearningPolicy()

    assert policy.evidence_collection_enabled is True
    assert policy.candidate_generation_enabled is True
    assert policy.promotion_enabled is False
    assert policy.auto_promotion_enabled is False


def test_skill_evidence_is_directional_and_context_specific() -> None:
    evidence = SkillEvidence(
        evidence_id="skill_evidence:1",
        actor_id="char_a",
        skill_id="first_aid",
        action_id="stabilize_injured_actor",
        binding_id="first_aid_to_stabilize",
        source_settlement_id="settlement:123",
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure", "state_interference"],
        evidence_channels={
            "acquisition": 0.0,
            "improvement": 0.12,
            "confidence": 0.03,
            "specialization": {"bleeding_control": 0.08},
            "tool_familiarity": {"clean_cloth": 0.04},
            "maladaptive_pattern": {},
        },
        eligible_for_candidate=False,
        eligible_for_promotion=False,
    )

    assert evidence.evidence_channels["improvement"] == 0.12
    assert evidence.evidence_channels["specialization"]["bleeding_control"] == 0.08
