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


def test_effective_profile_marks_required_claim():
    policy = CharacterMemoryRecallPolicy(pool_limit=1, token_budget=1)
    memory = {"knowledge_memories": [{"memory_id": "claim", "actor_id": "char_b", "claim": {"subject_ref": "door", "predicate": "state", "valid_at": 1}}]}
    import pytest
    with pytest.raises(MissingRequiredMemoryEvidence):
        CharacterSemanticRecallService(policy).select("char_b", {"memory": memory, "effective_profile": {"capability_constraint_layer": {"memory_retention": "strong"}}, "snapshot": {"current_attention_targets": ["door"]}}, turn_context=_turn())


def test_graph_budget_is_bounded_without_graph_writes():
    result = CharacterSemanticRecallService(max_graph_results=1).select("char_b", {"memory": {"event_memories": []}}, turn_context=_turn())
    assert result.incomplete_reason is None


def test_relation_scope_digest_mismatch_is_rejected():
    from types import SimpleNamespace
    from app.models.siming_heavenly_graph import GraphReaderContext
    service = CharacterSemanticRecallService()
    reader = GraphReaderContext(reader_principal="char_b", allowed_visibility_scopes=("actor_private",), world_id="w", session_id="s", story_branch_id="main", valid_at=10, recorded_at=10, policy_revision="policy:v1")
    relation = SimpleNamespace(scope=SimpleNamespace(world_id="w", session_id="s", story_branch_id="main", owner_actor_id="char_b"), validity=SimpleNamespace(contains=lambda _: True), recorded_at=1, semantic_metadata=SimpleNamespace(policy_revision="policy:v1", scope_digest="wrong"))
    result = SimpleNamespace(policy_revision="policy:v1", revision_vector={}, nodes=[], relations=[relation], selected_node_refs=[])
    assert service._validated_result(result, "char_b", _turn(), reader) == (False, "stale_read_set")


def test_relation_metadata_policy_mismatch_is_rejected():
    from types import SimpleNamespace
    from app.models.siming_heavenly_graph import GraphReaderContext
    service = CharacterSemanticRecallService()
    reader = GraphReaderContext(reader_principal="char_b", allowed_visibility_scopes=("actor_private",), world_id="w", session_id="s", story_branch_id="main", valid_at=10, recorded_at=10, policy_revision="policy:v1")
    relation = SimpleNamespace(scope=SimpleNamespace(world_id="w", session_id="s", story_branch_id="main", owner_actor_id="char_b"), validity=SimpleNamespace(contains=lambda _: True), recorded_at=1, semantic_metadata=SimpleNamespace(policy_revision="policy:v0", visibility_scope="actor_private", scope_digest="scope:actor-private"))
    result = SimpleNamespace(policy_revision="policy:v1", revision_vector={}, nodes=[], relations=[relation], selected_node_refs=[])
    assert service._validated_result(result, "char_b", _turn(), reader) == (False, "stale_read_set")


def test_runtime_generic_memory_revision_accepts_typed_graph_vector():
    from types import SimpleNamespace
    from app.models.siming_heavenly_graph import GraphReaderContext, GraphRevisionVector
    turn = CharacterTurnContext.begin("char_b", "evt:1", 10, causation_id="c", correlation_id="r", input_revision_vector={}, memory_revision_vector={"memory": 0}, policy_revision="policy:v1", snapshot_revision=1, branch_id="main")
    reader = GraphReaderContext(reader_principal="char_b", allowed_visibility_scopes=("actor_private",), world_id="w", session_id="s", story_branch_id="main", valid_at=10, recorded_at=10, policy_revision="policy:v1")
    result = SimpleNamespace(policy_revision="policy:v1", revision_vector=GraphRevisionVector(node_revision=2, relation_revision=1), nodes=[], relations=[], selected_node_refs=[])
    assert CharacterSemanticRecallService()._validated_result(result, "char_b", turn, reader) == (True, None)


def test_light_actor_without_scope_uses_bounded_memory_only():
    result = CharacterSemanticRecallService(graph=object(), scope_resolver=lambda _actor: None).select(
        "char_a", {"memory": {"event_memories": [{"memory_id": "e", "actor_id": "char_a"}]}}, turn_context=_turn("char_a")
    )
    assert result.selected_refs == ("event:e",)
