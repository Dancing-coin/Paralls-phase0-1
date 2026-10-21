import pytest

from app.character_agent.skills.evidence import (
    DIFFICULTY_FACTORS,
    LEARNING_STAGES,
    MASTERY_DIMENSIONS,
    ImitationEpisode,
    SkillEvidenceExtractor,
)
from app.character_agent.skills.models import ActionDefinition, ActionSettlementResult, SkillActionBinding, SkillDefinition, SkillEvaluationResult, LearningEpisode
from app.character_agent.skills.registry import CharacterSkillRegistry
from app.character_agent.skills.store import SkillEvidenceStore


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


def test_imitation_episode_preserves_provenance_stage_and_failure_evidence() -> None:
    episode = ImitationEpisode(
        episode_id="episode:imitate:1",
        learner_id="char_a",
        object_id="first_aid.basic_bandage@2",
        skill_id="first_aid",
        source_id="teacher:medic",
        source_refs=["observation:teacher:17"],
        context_revision="world:42",
        source_revision="teacher:medic@3",
        visible_context={"target": "actor:injured", "distance_m": 1.2},
        mode="observed_replay",
        action_error={"timing_error_ms": 91, "spatial_error_m": 0.42},
        resource_error={"bandage_count": 1, "resource_error": 0.18},
        pressure={"level": 0.4},
        interruptions=1,
        feedback=["late_recovery", "correct_target_line"],
        authority_accepted=False,
        review_refs=["review:episode:1"],
        stage="practiced",
    )
    assert episode.stage == "practiced"
    assert episode.source_refs == ["observation:teacher:17"]

    evidence = SkillEvidenceExtractor(registry=_registry()).extract(
        actor_id="char_a",
        selected_skill_path={
            "binding_id": "first_aid_to_stabilize",
            "skill_id": "first_aid",
            "skill_path_tags": ["medical"],
            "eligibility_status": "eligible",
        },
        skill_evaluation_result=SkillEvaluationResult(
            actor_id="char_a",
            action_id="stabilize_injured_actor",
            learning_policy_snapshot={"evidence_collection_enabled": True},
        ),
        settlement_result=ActionSettlementResult(
            outcome_band="failed",
            primary_failure_domain="physical_failure",
            failure_domains=["physical_failure"],
        ),
        source_settlement_id="settlement:episode:1",
        episode=episode,
    )

    assert evidence is not None
    assert evidence.evidence_channels["provenance"]["source_revision"] == "teacher:medic@3"
    assert evidence.evidence_channels["provenance"]["visible_context"]["target"] == "actor:injured"
    assert evidence.evidence_channels["failure"]["primary_domain"] == "physical_failure"
    assert set(evidence.evidence_channels["mastery"]) == set(MASTERY_DIMENSIONS)
    assert set(evidence.evidence_channels["difficulty"]) == set(DIFFICULTY_FACTORS)
    assert tuple(LEARNING_STAGES) == (
        "available", "noticed", "observed", "imitated", "structured", "practiced",
        "operational", "stable", "integrated", "personalized", "complete", "evolved",
    )


def test_evidence_extractor_fails_closed_for_missing_privacy_expiry_and_duplicate() -> None:
    evaluation = SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={"binding_id": "first_aid_to_stabilize", "skill_id": "first_aid", "eligibility_status": "eligible"},
        learning_policy_snapshot={"evidence_collection_enabled": True},
    )
    settlement = ActionSettlementResult(outcome_band="partial", primary_failure_domain="skill_failure")
    missing_source = SkillEvidenceExtractor(registry=_registry()).extract(
        actor_id="char_a", selected_skill_path=None, skill_evaluation_result=evaluation,
        settlement_result=settlement, source_settlement_id="settlement:missing",
        episode=LearningEpisode(episode_id="episode:missing", learner_id="char_a", skill_id="first_aid", stage="noticed"),
    )
    assert missing_source is None

    private_episode = LearningEpisode(
        episode_id="episode:private", learner_id="char_a", skill_id="first_aid", stage="noticed",
        source_refs=["observation:private"], source_privacy_scope="private:teacher", expires_at=10,
    )
    extractor = SkillEvidenceExtractor(registry=_registry())
    assert extractor.extract(
        actor_id="char_a", selected_skill_path=None, skill_evaluation_result=evaluation,
        settlement_result=settlement, source_settlement_id="settlement:private",
        episode=private_episode, allowed_privacy_scopes={"public"}, now_ts=9,
    ) is None
    assert extractor.extract(
        actor_id="char_a", selected_skill_path=None, skill_evaluation_result=evaluation,
        settlement_result=settlement, source_settlement_id="settlement:expired",
        episode=private_episode.model_copy(update={"source_privacy_scope": "public"}),
        allowed_privacy_scopes={"public"}, now_ts=10,
    ) is None

    store = SkillEvidenceStore()
    stored_extractor = SkillEvidenceExtractor(registry=_registry(), store=store)
    episode = private_episode.model_copy(update={"source_privacy_scope": "", "expires_at": None})
    first = stored_extractor.extract(
        actor_id="char_a", selected_skill_path=None, skill_evaluation_result=evaluation,
        settlement_result=settlement, source_settlement_id="settlement:once", episode=episode,
    )
    assert first is not None
    store.append(first)
    assert stored_extractor.extract(
        actor_id="char_a", selected_skill_path=None, skill_evaluation_result=evaluation,
        settlement_result=settlement, source_settlement_id="settlement:once", episode=episode,
    ) is None


def test_learning_projection_rejects_unknown_mastery_and_difficulty_keys() -> None:
    with pytest.raises(ValueError, match="unknown mastery dimension"):
        LearningEpisode(
            episode_id="episode:bad-mastery", learner_id="char_a", skill_id="first_aid", stage="noticed",
            mastery={"reaction_speed": {"value": 0.4}}, source_refs=["observation:1"],
        )
    with pytest.raises(ValueError, match="unknown difficulty factor"):
        LearningEpisode(
            episode_id="episode:bad-difficulty", learner_id="char_a", skill_id="first_aid", stage="noticed",
            difficulty={"luck": 0.4}, source_refs=["observation:1"],
        )
