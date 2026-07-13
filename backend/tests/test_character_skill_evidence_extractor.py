from app.character_agent.skills.evidence import SkillEvidenceExtractor
from app.character_agent.skills.models import (
    ActionSettlementResult,
    SkillEvaluationResult,
    SkillLearningPolicy,
)


def test_extractor_creates_directional_context_specific_evidence_from_successful_settlement() -> None:
    extractor = SkillEvidenceExtractor()
    evaluation_result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "action_id": "stabilize_injured_actor",
            "skill_path_tags": ["medical", "bleeding_control"],
            "learning": {
                "evidence_on_attempt": True,
                "evidence_on_blocked": False,
                "evidence_channels": ["improvement", "confidence", "specialization", "tool_familiarity"],
            },
            "tools_used": ["clean_cloth"],
        },
    )
    settlement_result = ActionSettlementResult(
        outcome_band="partial",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure"],
        skill_path_id="first_aid_to_stabilize",
        skill_contributions=["apply_pressure", "steady_hands"],
        risk_tags=["infection_risk"],
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation_result.selected_path,
        skill_evaluation_result=evaluation_result,
        settlement_result=settlement_result,
        learning_policy=SkillLearningPolicy(),
        source_settlement_id="settlement:123",
    )

    assert evidence is not None
    assert evidence.actor_id == "char_a"
    assert evidence.skill_id == "first_aid"
    assert evidence.action_id == "stabilize_injured_actor"
    assert evidence.binding_id == "first_aid_to_stabilize"
    assert evidence.source_settlement_id == "settlement:123"
    assert evidence.outcome_band == "partial"
    assert evidence.primary_failure_domain == "skill_failure"
    assert evidence.evidence_channels["improvement"] > 0.0
    assert evidence.evidence_channels["confidence"] > 0.0
    assert evidence.evidence_channels["specialization"]["medical"] > 0.0
    assert evidence.evidence_channels["specialization"]["bleeding_control"] > 0.0
    assert evidence.evidence_channels["tool_familiarity"]["clean_cloth"] > 0.0
    assert evidence.evidence_channels["context"]["skill_contributions"] == [
        "apply_pressure",
        "steady_hands",
    ]
    assert evidence.evidence_channels["context"]["risk_tags"] == ["infection_risk"]
    assert evidence.eligible_for_candidate is False
    assert evidence.eligible_for_promotion is False


def test_extractor_keeps_positive_progress_channels_zero_for_failed_settlement() -> None:
    extractor = SkillEvidenceExtractor()
    evaluation_result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "action_id": "stabilize_injured_actor",
            "learning": {
                "evidence_on_attempt": True,
                "evidence_on_blocked": False,
                "evidence_channels": ["improvement", "confidence"],
            },
        },
    )
    settlement_result = ActionSettlementResult(
        outcome_band="failed",
        primary_failure_domain="skill_failure",
        failure_domains=["skill_failure"],
        skill_path_id="first_aid_to_stabilize",
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation_result.selected_path,
        skill_evaluation_result=evaluation_result,
        settlement_result=settlement_result,
        learning_policy=SkillLearningPolicy(),
        source_settlement_id="settlement:failed",
    )

    assert evidence is not None
    assert evidence.outcome_band == "failed"
    assert evidence.evidence_channels["improvement"] == 0.0
    assert evidence.evidence_channels["confidence"] == 0.0


def test_extractor_returns_none_when_policy_disables_evidence_collection() -> None:
    extractor = SkillEvidenceExtractor()
    evaluation_result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "learning": {"evidence_on_attempt": True},
        },
    )
    settlement_result = ActionSettlementResult(
        outcome_band="clean_success",
        primary_failure_domain="none",
        skill_path_id="first_aid_to_stabilize",
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation_result.selected_path,
        skill_evaluation_result=evaluation_result,
        settlement_result=settlement_result,
        learning_policy=SkillLearningPolicy(evidence_collection_enabled=False),
        source_settlement_id="settlement:124",
    )

    assert evidence is None


def test_extractor_returns_none_when_selected_path_is_in_blocked_policy_domain() -> None:
    extractor = SkillEvidenceExtractor()
    evaluation_result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "special_override_to_stabilize",
            "skill_id": "first_aid",
            "skill_path_tags": ["special", "medical"],
            "learning": {"evidence_on_attempt": True},
        },
    )
    settlement_result = ActionSettlementResult(
        outcome_band="clean_success",
        primary_failure_domain="none",
        skill_path_id="special_override_to_stabilize",
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation_result.selected_path,
        skill_evaluation_result=evaluation_result,
        settlement_result=settlement_result,
        learning_policy=SkillLearningPolicy(),
        source_settlement_id="settlement:blocked-domain",
    )

    assert evidence is None


def test_extractor_returns_none_for_blocked_result_without_binding_policy_permission() -> None:
    extractor = SkillEvidenceExtractor()
    evaluation_result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "learning": {
                "evidence_on_attempt": True,
                "evidence_on_blocked": False,
                "evidence_channels": ["confidence", "maladaptive_pattern"],
            },
        },
    )
    settlement_result = ActionSettlementResult(
        outcome_band="blocked",
        primary_failure_domain="missing_requirement",
        failure_domains=["missing_requirement"],
        skill_path_id="first_aid_to_stabilize",
        missing_requirements=["first_aid.basic"],
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation_result.selected_path,
        skill_evaluation_result=evaluation_result,
        settlement_result=settlement_result,
        learning_policy=SkillLearningPolicy(),
        source_settlement_id="settlement:125",
    )

    assert evidence is None


def test_extractor_allows_blocked_evidence_when_binding_policy_permits_learning() -> None:
    extractor = SkillEvidenceExtractor()
    evaluation_result = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "skill_path_tags": ["medical"],
            "learning": {
                "evidence_on_attempt": True,
                "evidence_on_blocked": True,
                "evidence_channels": ["confidence", "maladaptive_pattern"],
            },
        },
    )
    settlement_result = ActionSettlementResult(
        outcome_band="blocked",
        primary_failure_domain="missing_requirement",
        failure_domains=["missing_requirement"],
        skill_path_id="first_aid_to_stabilize",
        missing_requirements=["first_aid.basic"],
    )

    evidence = extractor.extract(
        actor_id="char_a",
        selected_skill_path=evaluation_result.selected_path,
        skill_evaluation_result=evaluation_result,
        settlement_result=settlement_result,
        learning_policy=SkillLearningPolicy(),
        source_settlement_id="settlement:126",
    )

    assert evidence is not None
    assert evidence.outcome_band == "blocked"
    assert evidence.evidence_channels["confidence"] == 0.0
    assert evidence.evidence_channels["maladaptive_pattern"]["missing_requirement"] > 0.0
    assert evidence.evidence_channels["context"]["missing_requirements"] == ["first_aid.basic"]
    assert evidence.eligible_for_promotion is False
