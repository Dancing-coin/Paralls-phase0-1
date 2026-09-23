from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy, MissingRequiredMemoryEvidence
from app.character_agent.models.turn_context import CharacterTurnContext
from app.character_agent.services.character_semantic_recall import CharacterSemanticRecallService


def _turn(actor="char_b", branch="main"):
    return CharacterTurnContext.begin(actor, "evt:1", 10, causation_id="c", correlation_id="r",
        input_revision_vector={}, memory_revision_vector={"node_revision": 2}, policy_revision="policy:v1", snapshot_revision=1, branch_id=branch)


def test_semantic_recall_uses_canonical_refs_and_cards():
    result = CharacterSemanticRecallService().select("char_b", {"memory": {"event_memories": [{"memory_id": "door-opened:1", "actor_id": "char_b", "world_ts": 1}]}}, turn_context=_turn())
    assert result.selected_refs == ("event:door-opened:1",)
    assert result.cards_by_ref["event:door-opened:1"].source_refs == ()


def test_semantic_recall_rejects_cross_actor_memory():
    try:
        CharacterSemanticRecallService().select("char_b", {"memory": {"event_memories": [{"memory_id": "private", "actor_id": "char_a"}]}}, turn_context=_turn())
    except ValueError as exc:
        assert "actor scope" in str(exc)
    else:
        raise AssertionError("cross actor memory must be rejected")


def test_required_memory_evidence_blocks_before_model():
    policy = CharacterMemoryRecallPolicy(pool_limit=1, token_budget=1)
    memory = {"knowledge_memories": [{"memory_id": "claim", "actor_id": "char_b", "claim": {"subject_ref": "door", "predicate": "state", "valid_at": 1}}], "event_memories": []}
    try:
        CharacterSemanticRecallService(policy).select("char_b", {"memory": memory, "profile": {"capability_constraint_layer": {"memory_retention": "strong"}}, "snapshot": {"current_attention_targets": ["door"]}}, turn_context=_turn())
    except MissingRequiredMemoryEvidence:
        pass

