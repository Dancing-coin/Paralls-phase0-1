from __future__ import annotations

from pathlib import Path

import pytest

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    RelationLookupQuery,
)
from app.services.heavenly_graph_queries import HeavenlyGraphSemanticQueryFacade
from app.services.heavenly_graph_consistency import HeavenlyGraphConsistencyAudit
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import HeavenlyGraphReferentialIntegrityError
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(namespace: str, branch: str = "branch:main", owner: str | None = None) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:endpoint-scope",
        session_id="session:endpoint-scope",
        story_branch_id=branch,
        graph_namespace=namespace,
        owner_actor_id=owner,
    )


def _node(node_id: str, scope: HeavenlyGraphScope, *, visibility: str, node_type: str) -> HeavenlyGraphNode:
    source_ref = f"authority:{node_id}"
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type=node_type,
        scope=scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        attributes={},
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref=source_ref,
            causation_id=source_ref,
            correlation_id="corr:endpoint-scope",
            producer_system="test",
            evidence_refs=[source_ref],
        ),
        semantic_metadata=GraphSemanticMetadata(
            record_kind="projection",
            visibility_scope=visibility,
            derivation_kind="projection",
            source_event_refs=(source_ref,),
            policy_revision="policy:v1",
            scope_digest="scope:endpoint-scope",
        ),
    )


def _relation(
    relation_id: str,
    writer_scope: HeavenlyGraphScope,
    source: HeavenlyGraphNode,
    target: HeavenlyGraphNode,
) -> HeavenlyGraphRelation:
    return HeavenlyGraphRelation(
        relation_id=relation_id,
        relation_type="observed_as",
        source_node_id=source.node_id,
        target_node_id=target.node_id,
        scope=writer_scope,
        source_scope=source.scope,
        target_scope=target.scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        attributes={},
        provenance=GraphProvenance(
            source_kind="authority_event",
            source_ref=f"authority:{relation_id}",
            causation_id=f"authority:{relation_id}",
            correlation_id="corr:endpoint-scope",
            producer_system="test",
        ),
        semantic_metadata=GraphSemanticMetadata(
            record_kind="projection",
            visibility_scope="siming_internal",
            derivation_kind="projection",
            source_event_refs=(f"authority:{relation_id}",),
            policy_revision="policy:v1",
            scope_digest="scope:endpoint-scope",
        ),
    )


def _batch(scope: HeavenlyGraphScope, key: str, *, nodes: list[HeavenlyGraphNode] = (), relations: list[HeavenlyGraphRelation] = ()) -> HeavenlyGraphWriteBatch:
    return HeavenlyGraphWriteBatch(
        transaction_id=f"tx:endpoint:{key}",
        idempotency_key=f"idem:endpoint:{key}",
        scope=scope,
        nodes=list(nodes),
        relations=list(relations),
    )


def _context(scope: HeavenlyGraphScope, *, principal: str, scopes: tuple[str, ...]) -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal=principal,
        allowed_visibility_scopes=scopes,
        world_id=scope.world_id,
        session_id=scope.session_id,
        story_branch_id=scope.story_branch_id,
        valid_at=10,
        recorded_at=10,
        policy_revision="policy:v1",
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    adapter = (
        InMemoryHeavenlyGraphAdapter()
        if request.param == "memory"
        else SQLiteHeavenlyGraphAdapter(tmp_path / "endpoint-scopes.sqlite3")
    )
    yield adapter
    if isinstance(adapter, SQLiteHeavenlyGraphAdapter):
        adapter.close()


def test_cross_namespace_relation_admits_and_reads_from_distinct_endpoint_scopes(graph: object) -> None:
    actor_scope = _scope("actor_private", owner="char:b")
    siming_scope = _scope("siming_heavenly")
    actor = _node("view:char-b", actor_scope, visibility="actor_private", node_type="actor_view")
    world = _node("fact:letter", siming_scope, visibility="siming_internal", node_type="causal_event")
    graph.write_batch(_batch(actor_scope, "actor", nodes=[actor]))
    graph.write_batch(_batch(siming_scope, "world", nodes=[world]))
    relation = _relation("relation:observation", siming_scope, actor, world)

    graph.write_batch(_batch(siming_scope, "relation", relations=[relation]))

    result = graph.query_semantic(
        RelationLookupQuery(
            context=_context(siming_scope, principal="char:b", scopes=("actor_private", "siming_internal")),
            scope=siming_scope,
            relation_ids=[relation.relation_id],
        )
    )
    assert [item.relation_id for item in result.relations] == [relation.relation_id]
    assert result.relations[0].source_scope == actor_scope
    assert result.relations[0].target_scope == siming_scope


def test_cross_namespace_relation_fails_when_endpoint_is_missing(graph: object) -> None:
    actor_scope = _scope("actor_private", owner="char:b")
    siming_scope = _scope("siming_heavenly")
    actor = _node("view:missing", actor_scope, visibility="actor_private", node_type="actor_view")
    world = _node("fact:known", siming_scope, visibility="siming_internal", node_type="causal_event")
    graph.write_batch(_batch(siming_scope, "world-only", nodes=[world]))
    with pytest.raises(HeavenlyGraphReferentialIntegrityError):
        graph.write_batch(_batch(siming_scope, "missing-endpoint", relations=[_relation("relation:missing", siming_scope, actor, world)]))


def test_cross_namespace_relation_is_hidden_when_one_endpoint_is_not_visible(graph: object) -> None:
    actor_scope = _scope("actor_private", owner="char:b")
    siming_scope = _scope("siming_heavenly")
    actor = _node("view:hidden", actor_scope, visibility="actor_private", node_type="actor_view")
    world = _node("fact:visible", siming_scope, visibility="siming_internal", node_type="causal_event")
    graph.write_batch(_batch(actor_scope, "actor-hidden", nodes=[actor]))
    graph.write_batch(_batch(siming_scope, "world-visible", nodes=[world]))
    relation = _relation("relation:hidden-endpoint", siming_scope, actor, world)
    graph.write_batch(_batch(siming_scope, "hidden-relation", relations=[relation]))

    result = graph.query_semantic(
        RelationLookupQuery(
            context=_context(siming_scope, principal="reader:other", scopes=("siming_internal",)),
            scope=siming_scope,
            relation_ids=[relation.relation_id],
        )
    )
    assert result.relations == []
    assert result.incomplete_reason == "visibility_denied"


def test_sqlite_restart_preserves_endpoint_scope(tmp_path: Path) -> None:
    actor_scope = _scope("actor_private", owner="char:b")
    siming_scope = _scope("siming_heavenly")
    actor = _node("view:restart", actor_scope, visibility="actor_private", node_type="actor_view")
    world = _node("fact:restart", siming_scope, visibility="siming_internal", node_type="causal_event")
    database = tmp_path / "restart-endpoint-scopes.sqlite3"
    graph = SQLiteHeavenlyGraphAdapter(database)
    graph.write_batch(_batch(actor_scope, "restart-actor", nodes=[actor]))
    graph.write_batch(_batch(siming_scope, "restart-world", nodes=[world]))
    graph.write_batch(_batch(siming_scope, "restart-relation", relations=[_relation("relation:restart", siming_scope, actor, world)]))
    graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(database)
    stored = reopened.get_relation(relation_id="relation:restart", scope=siming_scope, valid_at=10)
    assert stored is not None
    assert stored.source_scope == actor_scope
    assert stored.target_scope == siming_scope
    reopened.close()


def test_cross_namespace_relation_audit_and_causal_query_resolve_endpoint_scopes(graph: object) -> None:
    actor_scope = _scope("actor_private", owner="char:b")
    siming_scope = _scope("siming_heavenly")
    actor = _node("view:causal", actor_scope, visibility="actor_private", node_type="actor_view")
    world = _node("fact:causal", siming_scope, visibility="siming_internal", node_type="causal_event")
    graph.write_batch(_batch(actor_scope, "causal-actor", nodes=[actor]))
    graph.write_batch(_batch(siming_scope, "causal-world", nodes=[world]))
    relation = _relation("relation:causal", siming_scope, actor, world)
    graph.write_batch(_batch(siming_scope, "causal-relation", relations=[relation]))
    context = _context(siming_scope, principal="char:b", scopes=("actor_private", "siming_internal"))
    report = HeavenlyGraphConsistencyAudit(graph).audit(siming_scope, context)
    assert report.errors == []
