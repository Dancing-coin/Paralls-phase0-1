from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery,
    CausalPathQuery,
    ConflictSetQuery,
    GraphProvenance,
    GraphReaderContext,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    NodeLookupQuery,
    RelationLookupQuery,
    PerspectiveQuery,
    SourceImpactQuery,
    HeavenlyGraphRelation,
    HeavenlyGraphWriteBatch,
)
from app.services.heavenly_graph_queries import HeavenlyGraphSemanticQueryFacade
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(namespace: str = "siming_heavenly", owner_actor_id: str | None = None) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:test",
        session_id="session:test",
        story_branch_id="branch:main",
        graph_namespace=namespace,
        owner_actor_id=owner_actor_id,
    )


def _context(*, scopes: tuple[str, ...] = ("public",), policy: str = "policy:v1") -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal="reader:siming",
        allowed_visibility_scopes=scopes,
        world_id="world:test",
        session_id="session:test",
        story_branch_id="branch:main",
        valid_at=10,
        recorded_at=10,
        policy_revision=policy,
    )


def _node(
    node_id: str,
    *,
    metadata: GraphSemanticMetadata | None = None,
    node_type: str = "world_fact",
    source_ref: str = "authority:test",
    scope: HeavenlyGraphScope | None = None,
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type=node_type,
        scope=scope or _scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref=source_ref,
            causation_id="cause:test",
            correlation_id="corr:test",
            producer_system="test",
        ),
        semantic_metadata=metadata or GraphSemanticMetadata(policy_revision="policy:v1", scope_digest="scope:test"),
    )


def test_semantic_query_models_require_explicit_reader_context() -> None:
    with pytest.raises(ValidationError):
        NodeLookupQuery(node_ids=["fact:one"])
    with pytest.raises(ValidationError):
        GraphReaderContext(
            reader_principal="reader:test",
            allowed_visibility_scopes=[],
            world_id="world:test",
            session_id="session:test",
            story_branch_id="branch:main",
            valid_at=1,
            policy_revision="policy:v1",
        )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    adapter = (
        InMemoryHeavenlyGraphAdapter()
        if request.param == "memory"
        else SQLiteHeavenlyGraphAdapter(tmp_path / "graph.db")
    )
    yield adapter
    if isinstance(adapter, SQLiteHeavenlyGraphAdapter):
        adapter.close()


def _write(graph: object, nodes: list[HeavenlyGraphNode]) -> None:
    from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch

    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:test",
            idempotency_key="query:test",
            scope=nodes[0].scope,
            nodes=nodes,
        )
    )


def test_semantic_node_lookup_returns_structured_deterministic_metadata(graph: object) -> None:
    _write(graph, [_node("fact:b"), _node("fact:a")])
    result = graph.query_semantic(NodeLookupQuery(context=_context(), limit=10))
    assert [node.node_id for node in result.nodes] == ["fact:a", "fact:b"]
    assert result.selected_node_refs == ["fact:a", "fact:b"]
    assert result.selected_relation_refs == []
    assert result.policy_revision == "policy:v1"
    assert result.scope_digest
    assert result.revision_vector.node_revision == 1
    assert result.truncated is False
    assert result.incomplete_reason is None


def test_semantic_query_excludes_proposals_and_does_not_leak_denied_existence(graph: object) -> None:
    _write(
        graph,
        [
            _node("fact:visible"),
            _node("proposal:hidden", node_type="policy_candidate", metadata=GraphSemanticMetadata(record_kind="proposal", visibility_scope="siming_internal", policy_revision="policy:v1")),
            _node("internal:hidden", node_type="causal_event", metadata=GraphSemanticMetadata(visibility_scope="siming_internal", policy_revision="policy:v1")),
        ],
    )
    result = graph.query_semantic(NodeLookupQuery(context=_context(), limit=10))
    assert [node.node_id for node in result.nodes] == ["fact:visible"]
    assert result.incomplete_reason == "visibility_denied"
    assert "proposal:hidden" not in result.selected_node_refs


def test_semantic_query_reports_stale_policy_without_returning_stale_records(graph: object) -> None:
    _write(graph, [_node("fact:stale", metadata=GraphSemanticMetadata(policy_revision="policy:old"))])
    result = graph.query_semantic(NodeLookupQuery(context=_context(policy="policy:v1"), limit=10))
    assert result.nodes == []
    assert result.incomplete_reason == "stale_read_set"


def test_relation_lookup_is_bounded_and_preserves_low_level_query_contract(graph: object) -> None:
    query = RelationLookupQuery(context=_context(), relation_types=["caused_by"], limit=3)
    assert query.limit == 3
    assert hasattr(graph, "query_nodes") and hasattr(graph, "query_relations")
    with pytest.raises(ValueError):
        NodeLookupQuery(context=_context(), limit=0)


def test_facade_maps_graph_failures_to_structured_unavailable_result() -> None:
    class BrokenGraph:
        def query_nodes(self, query: object) -> list[object]:
            raise RuntimeError("graph offline")

    result = HeavenlyGraphSemanticQueryFacade(BrokenGraph()).query(
        NodeLookupQuery(context=_context())
    )
    assert result.nodes == []
    assert result.incomplete_reason == "graph_unavailable"


def test_inaccessible_stale_private_record_reports_visibility_denied(graph: object) -> None:
    private_scope = _scope("actor_private", owner_actor_id="char_b")
    _write(
        graph,
        [
            _node(
                "private:stale",
                scope=private_scope,
                node_type="actor_view",
                metadata=GraphSemanticMetadata(
                    record_kind="projection",
                    visibility_scope="actor_private", policy_revision="policy:old"
                ),
            )
        ],
    )
    context = _context(scopes=("actor_private",)).model_copy(
        update={"reader_principal": "attacker:char_b"}
    )
    result = graph.query_semantic(
        NodeLookupQuery(context=context, scope=private_scope, limit=10)
    )
    assert result.nodes == []
    assert result.incomplete_reason == "visibility_denied"


def test_node_lookup_applies_source_filter_before_result_limit(graph: object) -> None:
    _write(
        graph,
        [
            _node("fact:a", source_ref="authority:other"),
            _node("fact:b", source_ref="authority:match"),
        ],
    )
    result = graph.query_semantic(
        NodeLookupQuery(context=_context(), source_refs=["authority:match"], limit=1)
    )
    assert [node.node_id for node in result.nodes] == ["fact:b"]
    assert result.truncated is False


def test_private_reader_authorization_uses_exact_canonical_principal(graph: object) -> None:
    private_scope = _scope("actor_private", owner_actor_id="char_b")
    _write(
        graph,
        [
            _node(
                "private:fact",
                scope=private_scope,
                node_type="actor_view",
                metadata=GraphSemanticMetadata(
                    record_kind="projection",
                    visibility_scope="actor_private", policy_revision="policy:v1"
                ),
            )
        ],
    )
    attacker = _context(scopes=("actor_private",)).model_copy(
        update={"reader_principal": "attacker:char_b"}
    )
    legitimate = attacker.model_copy(update={"reader_principal": "reader:char_b"})
    denied = graph.query_semantic(
        NodeLookupQuery(context=attacker, scope=private_scope, limit=10)
    )
    allowed = graph.query_semantic(
        NodeLookupQuery(context=legitimate, scope=private_scope, limit=10)
    )
    assert denied.nodes == []
    assert denied.incomplete_reason == "visibility_denied"
    assert [node.node_id for node in allowed.nodes] == ["private:fact"]


def test_node_lookup_marks_candidate_window_truncation_after_semantic_filter(graph: object) -> None:
    _write(
        graph,
        [
            _node(f"fact:{index:04d}", source_ref="authority:match")
            for index in range(1000)
        ],
    )
    result = graph.query_semantic(
        NodeLookupQuery(context=_context(), source_refs=["authority:match"], limit=10)
    )
    assert len(result.nodes) == 10
    assert result.truncated is True


def test_node_lookup_marks_filtered_results_over_requested_limit_as_truncated(graph: object) -> None:
    _write(
        graph,
        [
            _node("fact:match-a", source_ref="authority:match"),
            _node("fact:match-b", source_ref="authority:match"),
        ],
    )
    result = graph.query_semantic(
        NodeLookupQuery(context=_context(), source_refs=["authority:match"], limit=1)
    )
    assert [node.node_id for node in result.nodes] == ["fact:match-a"]
    assert result.truncated is True


def _relation(relation_id: str, source: str, target: str, relation_type: str = "caused_by", *, attrs: dict | None = None, scope: HeavenlyGraphScope | None = None, metadata: GraphSemanticMetadata | None = None) -> HeavenlyGraphRelation:
    return HeavenlyGraphRelation(
        relation_id=relation_id,
        relation_type=relation_type,
        source_node_id=source,
        target_node_id=target,
        scope=scope or _scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        attributes=attrs or {},
        provenance=GraphProvenance(source_kind="authority_event", source_ref="authority:test", causation_id="cause:test", correlation_id="corr:test", producer_system="test"),
        semantic_metadata=metadata or GraphSemanticMetadata(policy_revision="policy:v1"),
    )


def test_causal_path_query_traverses_registered_relations_and_bounds(graph: object) -> None:
    nodes = [_node(f"n:{i}") for i in range(4)]
    relations = [_relation("r:0", "n:0", "n:1"), _relation("r:1", "n:1", "n:2"), _relation("r:2", "n:2", "n:3")]
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:causal", idempotency_key="causal", scope=_scope(), nodes=nodes, relations=relations))
    result = graph.query_semantic(CausalPathQuery(context=_context(), seed_node_ids=["n:0"], max_depth=2, node_limit=3, relation_limit=2, max_paths=2))
    assert [node.node_id for node in result.nodes] == ["n:0", "n:1", "n:2"]
    assert [relation.relation_id for relation in result.relations] == ["r:0", "r:1"]
    assert result.truncated is True


def test_causal_path_max_paths_caps_returned_path_union_without_query_subgraph(graph: object, monkeypatch: pytest.MonkeyPatch) -> None:
    nodes = [_node(f"path:{index}") for index in range(3)]
    relations = [
        _relation("path:r-a", "path:0", "path:1"),
        _relation("path:r-b", "path:0", "path:2"),
    ]
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:path-limit", idempotency_key="path-limit", scope=_scope(), nodes=nodes, relations=relations))
    monkeypatch.setattr(graph, "query_subgraph", lambda **_: pytest.fail("semantic causal query must not call query_subgraph"))
    result = graph.query_semantic(CausalPathQuery(context=_context(), seed_node_ids=["path:0"], max_depth=1, node_limit=10, relation_limit=10, max_paths=1))
    assert [relation.relation_id for relation in result.relations] == ["path:r-a"]
    assert [node.node_id for node in result.nodes] == ["path:0", "path:1"]
    assert result.truncated is True


def test_causal_max_paths_caps_complete_paths_not_edges(graph: object) -> None:
    nodes = [_node(f"chain:{index}") for index in range(4)]
    relations = [
        _relation("chain:r0", "chain:0", "chain:1"),
        _relation("chain:r1", "chain:1", "chain:2"),
        _relation("chain:r2", "chain:2", "chain:3"),
    ]
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:chain-path", idempotency_key="chain-path", scope=_scope(), nodes=nodes, relations=relations))
    result = graph.query_semantic(CausalPathQuery(context=_context(), seed_node_ids=["chain:0"], max_depth=3, node_limit=10, relation_limit=10, max_paths=1))
    assert [relation.relation_id for relation in result.relations] == ["chain:r0", "chain:r1", "chain:r2"]
    assert [node.node_id for node in result.nodes] == ["chain:0", "chain:1", "chain:2", "chain:3"]
    assert result.truncated is False


def test_causal_explicit_noncausal_relation_filter_is_empty(graph: object) -> None:
    nodes = [_node("noncausal:source"), _node("noncausal:target")]
    relation = _relation("noncausal:r", "noncausal:source", "noncausal:target", relation_type="contradicts")
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:noncausal", idempotency_key="noncausal", scope=_scope(), nodes=nodes, relations=[relation]))
    result = graph.query_semantic(CausalPathQuery(context=_context(), seed_node_ids=["noncausal:source"], relation_types=["contradicts"], max_depth=2))
    assert result.nodes == []
    assert result.relations == []
    assert result.truncated is False


def test_causal_depth_boundary_reports_unexplored_outgoing_edges(graph: object) -> None:
    nodes = [_node("depth:source"), _node("depth:target")]
    relation = _relation("depth:r", "depth:source", "depth:target")
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:depth", idempotency_key="depth", scope=_scope(), nodes=nodes, relations=[relation]))
    result = graph.query_semantic(CausalPathQuery(context=_context(), seed_node_ids=["depth:source"], max_depth=0, max_paths=1))
    assert [node.node_id for node in result.nodes] == ["depth:source"]
    assert result.relations == []
    assert result.truncated is True


def test_causal_high_branching_stops_at_deterministic_work_budget(graph: object) -> None:
    branch_count = 64
    depth = 8
    root = _node("budget:root")
    nodes = [root]
    relations = []
    for branch_index in range(branch_count):
        previous_id = root.node_id
        for level in range(1, depth + 1):
            current_id = f"budget:{branch_index:02d}:{level}"
            nodes.append(_node(current_id))
            relations.append(
                _relation(
                    f"budget:r:{branch_index:02d}:{level}",
                    previous_id,
                    current_id,
                )
            )
            previous_id = current_id

    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:causal-budget",
            idempotency_key="causal-budget",
            scope=_scope(),
            nodes=nodes,
            relations=relations,
        )
    )
    result = graph.query_semantic(
        CausalPathQuery(
            context=_context(),
            seed_node_ids=[root.node_id],
            max_depth=depth,
            node_limit=100,
            relation_limit=100,
            max_paths=1,
        )
    )

    # The derived work budget is nine path-prefix work items here (one path
    # times its nine possible nodes). It stops deterministic BFS immediately
    # after admitting the root fan-out, rather than expanding all 64 chains.
    assert result.nodes == []
    assert result.relations == []
    assert result.truncated is True


def test_conflict_set_preserves_concurrent_claims_and_revisions(graph: object) -> None:
    first = _node("claim:a", metadata=GraphSemanticMetadata(policy_revision="policy:v1"))
    first = first.model_copy(update={"attributes": {"subject_ref": "world:x", "property_key": "mood"}})
    second = _node("claim:b", metadata=GraphSemanticMetadata(policy_revision="policy:v1"))
    second = second.model_copy(update={"attributes": {"subject_ref": "world:x", "property_key": "mood"}})
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:conflict", idempotency_key="conflict", scope=_scope(), nodes=[first, second]))
    result = graph.query_semantic(ConflictSetQuery(context=_context(), subject_ref="world:x", property_key="mood"))
    assert [node.node_id for node in result.nodes] == ["claim:a", "claim:b"]


def test_perspective_query_filters_actor_projection_without_leaking_other_actor(graph: object) -> None:
    own_scope = _scope("actor_private", owner_actor_id="char_b")
    other_scope = _scope("actor_private", owner_actor_id="char_c")
    own = _node("view:b", scope=own_scope, node_type="actor_view", metadata=GraphSemanticMetadata(visibility_scope="actor_private", record_kind="projection", policy_revision="policy:v1"))
    other = _node("view:c", scope=other_scope, node_type="actor_view", metadata=GraphSemanticMetadata(visibility_scope="actor_private", record_kind="projection", policy_revision="policy:v1"))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:perspective", idempotency_key="perspective-b", scope=own_scope, nodes=[own]))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:perspective", idempotency_key="perspective-c", scope=other_scope, nodes=[other]))
    context = _context(scopes=("actor_private",)).model_copy(update={"reader_principal": "reader:char_b"})
    result = graph.query_semantic(PerspectiveQuery(context=context, actor_ref="char_b", visibility_scopes=["actor_private"], scope=own_scope))
    assert [node.node_id for node in result.nodes] == ["view:b"]


def test_perspective_query_derives_actor_private_scope_when_omitted(graph: object) -> None:
    own_scope = _scope("actor_private", owner_actor_id="char_b")
    own = _node("view:implicit", scope=own_scope, node_type="actor_view", metadata=GraphSemanticMetadata(visibility_scope="actor_private", record_kind="projection", policy_revision="policy:v1"))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:implicit-perspective", idempotency_key="implicit-perspective", scope=own_scope, nodes=[own]))
    context = _context(scopes=("actor_private",)).model_copy(update={"reader_principal": "reader:char_b"})
    result = graph.query_semantic(PerspectiveQuery(context=context, actor_ref="char_b", visibility_scopes=["actor_private"]))
    assert [node.node_id for node in result.nodes] == ["view:implicit"]
    assert result.incomplete_reason is None


def test_behavior_turn_query_groups_by_turn_and_correlation(graph: object) -> None:
    turn = _node("turn:1", node_type="behavior_turn", metadata=GraphSemanticMetadata(visibility_scope="siming_internal", record_kind="projection", policy_revision="policy:v1"))
    turn = turn.model_copy(update={"attributes": {"turn_id": "turn-1", "stage": "settlement"}, "provenance": turn.provenance.model_copy(update={"correlation_id": "corr-1", "actor_id": "char_b"})})
    other = _node("turn:2", node_type="behavior_turn", metadata=GraphSemanticMetadata(visibility_scope="siming_internal", record_kind="projection", policy_revision="policy:v1"))
    other = other.model_copy(update={"attributes": {"turn_id": "turn-2", "stage": "settlement"}, "provenance": other.provenance.model_copy(update={"correlation_id": "corr-2", "actor_id": "char_b"})})
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:turn", idempotency_key="turn", scope=_scope(), nodes=[turn, other]))
    context = _context(scopes=("siming_internal",))
    result = graph.query_semantic(BehaviorTurnQuery(context=context, turn_id="turn-1", correlation_id="corr-1", actor_id="char_b", stage="settlement"))
    assert [node.node_id for node in result.nodes] == ["turn:1"]


def test_source_impact_query_finds_derived_records_for_source_revision(graph: object) -> None:
    source = _node("source:1")
    derived = _node("derived:1", node_type="causal_event", metadata=GraphSemanticMetadata(record_kind="projection", visibility_scope="public", source_event_refs=("source:1",), source_revision_vector=GraphRevisionVector(source_revision=7), policy_revision="policy:v1"))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:impact", idempotency_key="impact", scope=_scope(), nodes=[source, derived]))
    result = graph.query_semantic(SourceImpactQuery(context=_context(), source_ref="source:1", source_revision=7))
    assert [node.node_id for node in result.nodes] == ["derived:1"]


def test_source_impact_relation_endpoint_requires_derived_from_semantics(graph: object) -> None:
    nodes = [_node("source:relation"), _node("target:relation")]
    derived = _relation(
        "relation:derived",
        "source:relation",
        "target:relation",
        relation_type="derived_from",
        metadata=GraphSemanticMetadata(record_kind="projection", visibility_scope="siming_internal", policy_revision="policy:v1"),
    )
    unrelated = _relation("relation:unrelated", "source:relation", "target:relation")
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:source-relations", idempotency_key="source-nodes", scope=_scope(), nodes=nodes))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:source-relations", idempotency_key="source-relations", scope=_scope(), relations=[derived, unrelated]))
    result = graph.query_semantic(SourceImpactQuery(context=_context(scopes=("public", "siming_internal")), source_ref="source:relation"))
    assert [relation.relation_id for relation in result.relations] == ["relation:derived"]


def test_semantic_query_marks_raw_candidate_windows_truncated(graph: object) -> None:
    nodes = [_node(f"window:{index:04d}") for index in range(1000)]
    nodes[0] = nodes[0].model_copy(update={"attributes": {"subject_ref": "subject:window", "property_key": "state"}})
    nodes[1] = nodes[1].model_copy(update={"attributes": {"turn_id": "turn:window"}})
    nodes[2] = _node("window:derived", node_type="causal_event", metadata=GraphSemanticMetadata(record_kind="projection", visibility_scope="public", source_event_refs=("source:window",), policy_revision="policy:v1"))
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:window", idempotency_key="window-nodes", scope=_scope(), nodes=nodes))
    relations = [_relation(f"window:r:{index:04d}", "window:0000", "window:0001") for index in range(1000)]
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:window", idempotency_key="window-relations", scope=_scope(), relations=relations))
    assert graph.query_semantic(ConflictSetQuery(context=_context(), subject_ref="subject:window", property_key="state", limit=10)).truncated is True
    assert graph.query_semantic(BehaviorTurnQuery(context=_context(), turn_id="turn:window", limit=10)).truncated is True
    assert graph.query_semantic(SourceImpactQuery(context=_context(), source_ref="source:window", limit=10)).truncated is True


def test_perspective_query_marks_raw_candidate_window_truncated(graph: object) -> None:
    scope = _scope("actor_private", owner_actor_id="char_b")
    nodes = [
        _node(
            f"view:window:{index:04d}",
            scope=scope,
            node_type="actor_view",
            metadata=GraphSemanticMetadata(record_kind="projection", visibility_scope="actor_private", policy_revision="policy:v1"),
        )
        for index in range(1000)
    ]
    graph.write_batch(HeavenlyGraphWriteBatch(transaction_id="tx:perspective-window", idempotency_key="perspective-window", scope=scope, nodes=nodes))
    context = _context(scopes=("actor_private",)).model_copy(update={"reader_principal": "reader:char_b"})
    result = graph.query_semantic(PerspectiveQuery(context=context, actor_ref="char_b", limit=10))
    assert result.truncated is True
