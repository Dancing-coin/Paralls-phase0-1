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
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type=node_type,
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref="authority:test",
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
