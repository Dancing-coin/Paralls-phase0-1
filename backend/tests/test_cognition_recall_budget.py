from copy import deepcopy

import pytest

from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
from app.character_agent.cognition.cognition_policy import CognitionPolicy
from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy, MissingRequiredMemoryEvidence
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.reasoning.l2_reasoner import CharacterAgentL2Service
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.services.character_semantic_recall import CharacterSemanticRecallService
from app.models.character_agent_runtime import CharacterInterpretation
from app.models.siming_heavenly_graph import GraphReaderContext


def _inputs(limit=1, tokens=1000):
    turn = CharacterTurnContext.begin(
        "char_b", "evt:budget", 10, causation_id="c", correlation_id="r",
        input_revision_vector={}, memory_revision_vector={"memory": 0},
        policy_revision="policy:v1", snapshot_revision=1,
    )
    envelope = CapabilityEnvelope.compile(
        actor_id=turn.actor_id, turn_id=turn.turn_id,
        source_refs=[turn.source_event_ref], revision_pins={"policy_revision": turn.policy_revision},
    )
    raw = CognitionPolicy.resolve(envelope=envelope).model_dump(mode="json", exclude={"policy_digest"})
    raw["memory"] = {"recall_limit": limit, "token_budget": tokens}
    policy = CognitionPolicy.model_validate(raw)
    context = {
        "actor_id": turn.actor_id, "turn_id": turn.turn_id,
        "capability_envelope": envelope.model_dump(mode="json"),
        "cognition_policy": policy.model_dump(mode="json"),
        "memory": {pool: [
            {"memory_id": f"{pool}-{i}", "actor_id": turn.actor_id, "world_ts": i,
             "summary": f"private memory {pool}-{i}"} for i in range(3)
        ] for pool in ("event_memories", "observation_memories")},
    }
    return turn, context


@pytest.mark.parametrize("limit,tokens", [(1, 1000), (0, 1000), (10, 0), (10, 1)])
def test_frozen_policy_caps_total_recall_across_pools(limit, tokens):
    _, context = _inputs(limit, tokens)
    original = deepcopy(context)
    result = CharacterMemoryRecallPolicy().select(context["memory"], context=context,
        requirements={"minimum_pool_limit": 16, "minimum_token_budget": 2400})
    assert len(result.metadata["selected_memory_refs"]) <= limit
    assert result.metadata["estimated_tokens"] <= tokens
    assert result.metadata["cognition_policy_digest"] == context["cognition_policy"]["policy_digest"]
    assert result.metadata["truncated"]
    assert context == original


def test_semantic_card_truncation_also_bounds_memory_and_reports_omissions():
    turn, context = _inputs(limit=6)
    result = CharacterSemanticRecallService(card_budget=1).select("char_b", context, turn_context=turn)
    refs = {card.ref for card in result.cards}
    memory_refs = {f"{pool.split('_')[0]}:{entry['memory_id']}"
        for pool, entries in result.memory.items() for entry in entries
        if pool in {"event_memories", "observation_memories"}}
    assert len(refs) == 1
    assert memory_refs == refs == set(result.selected_refs)
    assert len(result.omitted_refs) == 5
    assert set(result.metadata["selected_memory_refs"]) == refs


def test_zero_recall_budget_does_not_query_graph(monkeypatch):
    turn, context = _inputs(limit=0)

    class Graph:
        def query_semantic(self, query):
            pytest.fail("zero recall must not issue graph queries")

    service = CharacterSemanticRecallService(graph=Graph())
    reader = GraphReaderContext(reader_principal="char_b", allowed_visibility_scopes=("actor_private",),
        world_id="w", session_id="s", story_branch_id="main", valid_at=10, recorded_at=10, policy_revision="policy:v1")
    monkeypatch.setattr(service, "_reader_context", lambda _: reader)
    result = service.select("char_b", context, turn_context=turn)
    assert not result.cards
    assert not any(result.memory.values())
    assert not result.selected_refs
    assert result.truncated


def test_required_memory_cannot_override_zero_frozen_budget():
    turn, context = _inputs(limit=0)
    context["profile"] = {"capability_constraint_layer": {"memory_retention": "strong"}}
    context["attention_targets"] = ["door"]
    context["memory"]["knowledge_memories"] = [{
        "memory_id": "required", "actor_id": "char_b",
        "claim": {"subject_ref": "door", "predicate": "state", "valid_at": 1},
    }]
    with pytest.raises(MissingRequiredMemoryEvidence):
        CharacterSemanticRecallService().select("char_b", context, turn_context=turn)


@pytest.mark.parametrize("field", ["actor_id", "turn_id"])
def test_foreign_policy_never_supplies_recall_budget(field):
    turn, context = _inputs()
    raw = context["cognition_policy"]
    raw.pop("policy_digest")
    raw[field] = "foreign"
    context["cognition_policy"] = CognitionPolicy.model_validate(raw).model_dump(mode="json")
    with pytest.raises(ValueError, match="cognition_contract_"):
        CharacterSemanticRecallService().select("char_b", context, turn_context=turn)


def test_l2_and_gateway_keep_same_budget_on_final_model_request():
    turn, context = _inputs(limit=1)
    request = CharacterAgentL2Service(semantic_recall_service=CharacterSemanticRecallService()).prepare_reasoning_request(
        snapshot=CharacterPrivateWorldSnapshot(actor_id="char_b", room_id="room", scene_id="scene",
            zone_id="zone", producer_ts=10, updated_at=10), event={},
        memory_bundle=context["memory"], turn_context=turn,
        capability_envelope=context["capability_envelope"], cognition_policy=context["cognition_policy"],
    )
    prepared = request["context"]
    assert len(prepared["semantic_cards"]) == 1
    assert len(prepared["memory_recall"]["selected_memory_refs"]) == 1
    assert prepared["memory_recall"]["cognition_policy_digest"] == context["cognition_policy"]["policy_digest"]
    again = CharacterModelGateway().prepare_run_request(task_kind="l3_planning", context=prepared)
    assert again["context"]["memory"] == prepared["memory"]
    assert again["context"]["memory_recall"]["token_budget"] <= 1000


@pytest.mark.parametrize("semantic", [False, True])
def test_l3_prepared_recall_cannot_bypass_frozen_policy(semantic):
    turn, context = _inputs(limit=1)
    service = CharacterAgentL3Service(semantic_recall_service=CharacterSemanticRecallService() if semantic else None)
    prepared = service.prepare_intent_plan(
        interpretation=CharacterInterpretation(actor_id="char_b", interpreted_summary="watch",
            interpretation_type="observation", salience_score=.5, ambiguity_level="low",
            risk_level="low", opportunity_level="low"), control_mode="agent_full_auto",
        memory_bundle=context["memory"], turn_context=turn,
        capability_envelope=context["capability_envelope"], cognition_policy=context["cognition_policy"],
    )
    import json
    request = json.loads(prepared.request_json)
    recall = request["context"]["memory_recall"]
    assert len(recall["selected_memory_refs"]) <= 1
    assert recall["cognition_policy_digest"] == context["cognition_policy"]["policy_digest"]
    if semantic:
        assert len(request["context"]["semantic_cards"]) <= 1
