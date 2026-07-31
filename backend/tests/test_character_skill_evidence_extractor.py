from app.character_agent.skills.evidence import SkillEvidenceExtractor
from app.character_agent.skills.models import ActionDefinition, ActionSettlementResult, SkillActionBinding, SkillDefinition, SkillEvaluationResult
from app.character_agent.skills.registry import CharacterSkillRegistry


def _registry(*, blocked_learning: bool = False) -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[SkillDefinition(skill_id="first_aid", display_name="First Aid", domains=["medical"])],
        actions=[ActionDefinition(action_id="stabilize_injured_actor", kind="composite")],
        bindings=[
            SkillActionBinding(
                binding_id="first_aid_to_stabilize",
                skill_id="first_aid",
                action_id="stabilize_injured_actor",
                skill_path_tags=["medical", "bleeding_control"],
                learning={
                    "evidence_on_attempt": True,
                    "evidence_on_blocked": blocked_learning,
                },
            )
        ],
    )


def test_extracts_directional_evidence_for_successful_attempt() -> None:
    extractor = SkillEvidenceExtractor(registry=_registry())
    evaluation = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "skill_path_tags": ["medical", "bleeding_control"],
            "eligibility_status": "eligible",
        },
        learning_policy_snapshot={
            "evidence_collection_enabled": True,
            "candidate_generation_enabled": True,
            "promotion_enabled": False,
        },
    )
    settlement = ActionSettlementResult(
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure"],
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation.selected_path,
        skill_evaluation_result=evaluation,
        settlement_result=settlement,
        source_settlement_id="settlement:1",
    )

    assert evidence is not None
    assert evidence.skill_id == "first_aid"
    assert evidence.evidence_channels["improvement"] > 0.0
    assert evidence.evidence_channels["specialization"]["medical"] > 0.0
    assert evidence.eligible_for_candidate is True
    assert evidence.eligible_for_promotion is False


def test_skips_evidence_when_policy_disables_collection() -> None:
    extractor = SkillEvidenceExtractor(registry=_registry())
    evaluation = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={"binding_id": "first_aid_to_stabilize", "skill_id": "first_aid"},
        learning_policy_snapshot={"evidence_collection_enabled": False},
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation.selected_path,
        skill_evaluation_result=evaluation,
        settlement_result=ActionSettlementResult(outcome_band="clean_success"),
        source_settlement_id="settlement:1",
    )

    assert evidence is None


def test_blocked_paths_only_emit_evidence_when_binding_policy_allows_it() -> None:
    blocked_evaluation = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        blocked_paths=[
            {
                "binding_id": "first_aid_to_stabilize",
                "skill_id": "first_aid",
                "skill_path_tags": ["medical"],
                "eligibility_status": "blocked",
            }
        ],
        learning_policy_snapshot={
            "evidence_collection_enabled": True,
            "candidate_generation_enabled": True,
        },
    )
    settlement = ActionSettlementResult(
        outcome_band="blocked",
        primary_failure_domain="missing_requirement",
        failure_domains=["missing_requirement"],
    )

    blocked_off = SkillEvidenceExtractor(registry=_registry(blocked_learning=False)).extract(
        actor_id="char_a",
        selected_skill_path=None,
        skill_evaluation_result=blocked_evaluation,
        settlement_result=settlement,
        source_settlement_id="settlement:blocked-off",
    )
    blocked_on = SkillEvidenceExtractor(registry=_registry(blocked_learning=True)).extract(
        actor_id="char_a",
        selected_skill_path=None,
        skill_evaluation_result=blocked_evaluation,
        settlement_result=settlement,
        source_settlement_id="settlement:blocked-on",
    )

    assert blocked_off is None
    assert blocked_on is not None
    assert blocked_on.evidence_channels["improvement"] == 0.0
    assert blocked_on.eligible_for_candidate is False
