from __future__ import annotations

from app.character_agent.skills.models import PrimitiveActionPlan, SkillEvaluationResult
from app.character_agent.skills.evidence import LearningEpisode
from app.character_agent.skills.learning import LearningProposal
from app.character_agent.skills.settlement import SkillLearningSettlement
from app.character_agent.skills.store import SkillEvidenceStore
from app.services.interaction_orchestration_service import InteractionOrchestrationService, StructuredInteractionRequest
from app.world_runtime.intelligence_upgrade import InteractionIntentFrame


def _request(**overrides: object) -> StructuredInteractionRequest:
    payload = {
        "intent": InteractionIntentFrame(
            intent_id="intent:inspect",
            actor_id="char_a",
            target_refs={"object_ids": ["obj_box"]},
            semantic_intent="inspect",
        ),
        "player_id": "player",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "producer_ts": 1,
        "target_object_id": "obj_box",
    }
    payload.update(overrides)
    return StructuredInteractionRequest(**payload)


def _blocked_skill_evaluation() -> SkillEvaluationResult:
    return SkillEvaluationResult(
        actor_id="char_a",
        action_id="stabilize_injured_actor",
        selected_path={},
        viable_paths=[],
        blocked_paths=[{"binding_id": "bandage_path", "missing_requirements": ["tool.bandage"]}],
        recommendation_reason=["fallback_blocked"],
        learning_policy_snapshot={"promotion_enabled": False},
    )


def _primitive_action_plan() -> PrimitiveActionPlan:
    return PrimitiveActionPlan(
        composite_action_id="stabilize_injured_actor",
        skill_path_id="bandage_path",
        primitive_actions=["approach_target", "inspect_wound"],
        realization_keys=["approach_careful"],
    )


def test_settlement_metadata_stays_advisory_for_accepted_results() -> None:
    service = InteractionOrchestrationService()
    base_result = service.execute(_request())
    result = service.execute(
        _request(
            skill_evaluation_result=SkillEvaluationResult(
                actor_id="char_a",
                action_id="inspect_object",
                selected_path={"binding_id": "inspect_path", "skill_id": "observation"},
                viable_paths=[{"binding_id": "inspect_path", "expected_quality": "clean_success"}],
                blocked_paths=[],
                recommendation_reason=[],
                learning_policy_snapshot={"promotion_enabled": False},
            ),
            primitive_action_plan=PrimitiveActionPlan(
                composite_action_id="inspect_object",
                skill_path_id="inspect_path",
                primitive_actions=["orient_to_target", "focus_view"],
                realization_keys=["focus_view"],
            ),
        )
    )

    assert result.status == base_result.status == "completed"
    assert result.unified_result_family == base_result.unified_result_family
    assert result.channel_results[0].payload == base_result.channel_results[0].payload
    assert result.action_settlement_result is not None
    assert result.action_settlement_result.outcome_band == "clean_success"
    assert result.action_settlement_result.primary_failure_domain == "none"
    assert result.action_settlement_result.failure_domains == []


def test_settlement_metadata_does_not_override_rejected_authority_results() -> None:
    service = InteractionOrchestrationService()
    base_result = service.execute(_request(constraint_refs=["constraint:locked"]))
    result = service.execute(
        _request(
            constraint_refs=["constraint:locked"],
            skill_evaluation_result=_blocked_skill_evaluation(),
            primitive_action_plan=_primitive_action_plan(),
        )
    )

    assert result.status == base_result.status == "denied"
    assert result.unified_result_family == base_result.unified_result_family
    assert result.channel_results[0].payload == base_result.channel_results[0].payload
    assert result.action_settlement_result is not None
    assert result.action_settlement_result.outcome_band == "blocked"
    assert result.action_settlement_result.primary_failure_domain == "missing_requirement"
    assert result.action_settlement_result.failure_domains == ["missing_requirement"]
    assert result.unified_result_family[0]["settlement_status"] == "rejected"


def test_orchestration_records_policy_allowed_skill_evidence_without_changing_authority_result() -> None:
    service = InteractionOrchestrationService()
    result = service.execute(
        _request(
            skill_evaluation_result=SkillEvaluationResult(
                actor_id="char_a",
                action_id="inspect_object",
                selected_path={
                    "binding_id": "inspect_path",
                    "skill_id": "observation",
                    "skill_path_tags": ["observe"],
                    "eligibility_status": "eligible",
                },
                viable_paths=[{"binding_id": "inspect_path"}],
                learning_policy_snapshot={"evidence_collection_enabled": True},
            )
        )
    )

    assert result.status == "completed"
    assert result.skill_evidence is not None
    assert result.skill_evidence.eligible_for_promotion is False
    assert service.skill_evidence_store.query(actor_id="char_a") == [result.skill_evidence]


def test_learning_owner_settlement_replays_exact_duplicate_and_rejects_changed_duplicate() -> None:
    store = SkillEvidenceStore()
    service = SkillLearningSettlement(store=store)
    proposal = LearningProposal(
        proposal_id="proposal:1",
        idempotency_key="learn:char_a:first_aid:1",
        actor_id="char_a",
        skill_id="first_aid",
        object_id="first_aid.basic_bandage@2",
        episode_id="episode:1",
        stage="practiced",
        operation="upgrade",
        evidence_refs=["evidence:1"],
        source_revision="teacher:medic@2",
    )

    accepted = service.settle(proposal, authority_event_id="authority:learn:1")
    duplicate = service.settle(proposal, authority_event_id="authority:learn:1")
    changed = service.settle(
        proposal.model_copy(update={"stage": "operational"}),
        authority_event_id="authority:learn:1",
    )

    assert accepted.status == "accepted"
    assert duplicate.status == "duplicate_replayed"
    assert duplicate.revision == accepted.revision
    assert changed.status == "changed_duplicate"
    assert changed.revision == accepted.revision
    assert store.skill_revision(actor_id="char_a", skill_id="first_aid") == accepted.revision


def test_failed_learning_settlement_retains_failure_evidence_without_profile_mutation() -> None:
    store = SkillEvidenceStore()
    service = SkillLearningSettlement(store=store)
    proposal = LearningProposal(
        proposal_id="proposal:failed",
        idempotency_key="learn:char_a:first_aid:failed",
        actor_id="char_a",
        skill_id="first_aid",
        object_id="first_aid.basic_bandage@2",
        episode_id="episode:failed",
        stage="practiced",
        operation="upgrade",
        evidence_refs=["evidence:failure"],
        source_revision="teacher:medic@2",
        failure_refs=["failure:physical_failure"],
    )

    rejected = service.settle(proposal, authority_event_id="", accepted=False, reason="owner_rejected")

    assert rejected.status == "rejected"
    assert rejected.revision == 0
    assert store.skill_revision(actor_id="char_a", skill_id="first_aid") == 0
    assert store.failure_evidence(actor_id="char_a", skill_id="first_aid") == ["failure:physical_failure"]
