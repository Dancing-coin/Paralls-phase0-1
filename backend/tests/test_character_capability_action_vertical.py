"""Plan02 Task6 contract verticals; no model-quality or scene admission claim."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.profile.loader import CharacterProfileLoader
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.skills.catalog import create_runtime_skill_registry
from app.character_agent.skills.evidence import SkillEvidenceExtractor
from app.character_agent.skills.learning import SkillCandidateStore, SkillLearningGate
from app.character_agent.skills.models import ActionSettlementResult, LearningEpisode, SkillEvaluationResult
from app.character_agent.skills.service import CharacterSkillService
from app.character_agent.skills.settlement import SkillLearningSettlement
from app.character_agent.skills.store import SkillEvidenceStore
from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from test_character_agent_l2_reasoning import _LocalGateway


@pytest.mark.parametrize("actor_id", ["char_a", "char_b", "char_c"])
def test_authored_actor_l2_l3_frozen_capability_to_l4(actor_id):
    profile = CharacterProfileLoader().load(actor_id).model_dump(mode="json")
    before = deepcopy(profile)
    skills = CharacterSkillService(registry=create_runtime_skill_registry())
    states = skills.initial_skill_states(actor_id=actor_id, profile=profile)
    stable = skills.compile_stable_snapshot(actor_id=actor_id, skill_states=states)
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id=actor_id, room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", producer_ts=10, updated_at=10,
    )
    event = CharacterPerceivedEvent(
        actor_id=actor_id, percept_channel="visual", producer_ts=10,
        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
        perceived_summary="档案室门锁被动过；无人知道是谁动的",
        source_candidate_event_id="event:lock:10", clarity_score=.8, certainty_score=.6,
    )
    turn = CharacterTurnContext.begin(
        actor_id=actor_id, source_event_ref=event.source_candidate_event_id,
        producer_ts=10, causation_id="cause:lock:10", correlation_id="corr:lock:10",
        input_revision_vector={f"session:{actor_id}": 1}, memory_revision_vector={},
        policy_revision=f"policy:{actor_id}:1", snapshot_revision=1, branch_id="branch:main",
    )
    gateway = _LocalGateway()
    interpretation = CharacterAgentL2Service(gateway=gateway).interpret_perceived_event(
        snapshot, event, effective_profile=profile, turn_context=turn,
    )
    planner = CharacterAgentL3Service(gateway=gateway)
    prepared = planner.prepare_intent_plan(
        interpretation=interpretation, control_mode="agent_full_auto",
        snapshot=snapshot.model_dump(), profile=profile, turn_context=turn,
        skill_affordance_summary={"stable_ability_snapshot": stable.model_dump(mode="json")},
    )
    envelope = prepared.capability_envelope
    policy = prepared.cognition_policy
    assert envelope["actor_id"] == policy["actor_id"] == actor_id
    assert envelope["turn_id"] == policy["turn_id"] == turn.turn_id
    assert envelope["capability_revision"] == stable.capability_revision
    assert policy["envelope_digest"] == envelope["envelope_digest"]
    assert len(prepared.candidate_mapping) <= envelope["cognitive_limits"]["max_candidate_intents"]
    frozen = deepcopy(prepared.candidate_mapping)
    output = gateway.complete_prepared_request(prepared.request_json)
    plan = planner.finish_intent_plan(prepared, output)
    decision = planner.decision_from_plan(plan, interpretation=interpretation)
    contract = CharacterAgentL4Executor().build_execution_contract(snapshot, interpretation, decision, turn)
    assert prepared.candidate_mapping == frozen
    assert contract.turn_id == turn.turn_id
    assert contract.actor_ref == f"character:{actor_id}"
    assert contract.semantic_intent_id == decision.selected_intent
    assert list(contract.target_refs) == decision.target_refs
    assert contract.correlation_id == turn.correlation_id
    assert decision.planning_status == "continuity_floor"
    assert profile == before
    assert skills.compile_stable_snapshot(actor_id=actor_id, skill_states=states) == stable


def test_fourth_source_authored_role_remains_outside_runtime_admission():
    fixture = yaml.safe_load((Path(__file__).parent / "fixtures/character_evaluation/char_d_authored/profile.yaml").read_text(encoding="utf-8"))
    assert fixture["schema_mapping"]["runtime_admission"] is False
    assert {"hard_limits", "compute_defaults"}.issubset(fixture["unresolved_fields"])
    with pytest.raises(FileNotFoundError):
        CharacterProfileLoader().load("char_d")


# Original role14 learning archetypes are route fixtures, not scene identities.
@pytest.mark.parametrize("route,methods,stages,operation", [
    ("disciplined_swordsman", ("imitation", "decomposition", "repetition"), ("imitated", "structured", "stable"), "upgrade"),
    ("curious_mage", ("research", "cross_domain_fusion", "controlled_variant"), ("observed", "integrated", "personalized"), "fusion"),
    ("anxious_healer", ("instruction", "low_risk_practice", "cooperative_field"), ("noticed", "practiced", "operational"), "upgrade"),
    ("intuitive_hunter", ("observation", "rapid_imitation", "field_feedback"), ("observed", "imitated", "practiced"), "upgrade"),
])
def test_learning_route_evidence_proposal_and_missing_owner_preserve_profile(route, methods, stages, operation):
    profile = CharacterProfileLoader().load("char_a").model_dump(mode="json")
    before = deepcopy(profile)
    registry = create_runtime_skill_registry()
    skills = CharacterSkillService(registry=registry)
    states = skills.initial_skill_states(actor_id="char_a", profile=profile)
    stable = skills.compile_stable_snapshot(actor_id="char_a", skill_states=states)
    gate = SkillLearningGate()
    store = SkillEvidenceStore()
    owner_boundary = SkillLearningSettlement(store=store)
    candidates = SkillCandidateStore(registry=registry)
    for index, (method, stage) in enumerate(zip(methods, stages)):
        episode = LearningEpisode(
            episode_id=f"episode:{route}:{index}", actor_id="char_a", skill_id="observation",
            object_id="observation@1", source_id="event:lock:10", source_revision="event:lock:10@1",
            source_refs=["event:lock:10"], evidence_refs=[f"feedback:{route}:{index}"],
            context_revision="scene_demo:1", stage=stage, learning_method=method,
        )
        admitted = gate.evaluate(episode, current_source_revision="event:lock:10@1", current_context_revision="scene_demo:1", operation=operation)
        assert admitted.accepted and admitted.proposal is not None
        evaluation = SkillEvaluationResult(
            actor_id="char_a", action_id="inspect_object",
            selected_path={"skill_id": "observation", "binding_id": "inspect_path", "eligibility_status": "eligible"},
            learning_policy_snapshot={"evidence_collection_enabled": True, "candidate_generation_enabled": True, "promotion_enabled": False},
        )
        evidence = SkillEvidenceExtractor(registry=registry).extract(
            actor_id="char_a", selected_skill_path=evaluation.selected_path,
            skill_evaluation_result=evaluation, settlement_result=ActionSettlementResult(outcome_band="partial", primary_failure_domain="skill_failure", failure_domains=["skill_failure"]),
            source_settlement_id=f"diagnostic:{route}:{index}", episode=episode,
        )
        assert evidence is not None
        candidates.observe(evidence)
        proposal = admitted.proposal.model_copy(update={"failure_refs": [f"feedback:{route}:{index}"]})
        receipt = owner_boundary.settle(proposal, authority_event_id="")
        assert receipt.status == "rejected" and receipt.reason == "authority_required"
        assert f"feedback:{route}:{index}" in store.failure_evidence(actor_id="char_a", skill_id="observation")
        assert store.skill_revision(actor_id="char_a", skill_id="observation") == 0
        stale = gate.evaluate(episode, current_source_revision="event:lock:10@2", operation=operation)
        assert not stale.accepted and "stale_source" in stale.reasons
    assert candidates.progress(actor_id="char_a", skill_id="observation")["stage"] == stages[-1]
    assert profile == before
    assert skills.compile_stable_snapshot(actor_id="char_a", skill_states=states) == stable
