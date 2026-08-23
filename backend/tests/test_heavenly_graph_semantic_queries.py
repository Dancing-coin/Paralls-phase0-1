from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphScope,
    NodeLookupQuery,
    RelationLookupQuery,
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
