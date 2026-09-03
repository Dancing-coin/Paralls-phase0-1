from pathlib import Path

import pytest

from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery,
    CausalPathQuery,
    ConflictSetQuery,
    GraphBranchDiffQuery,
    GraphBranchForkRequest,
    GraphBranchLifecycleRequest,
    GraphCorrectionRequest,
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery,
    NodeLookupQuery,
    RelationLookupQuery,
    SourceImpactQuery,
)
from app.services.heavenly_graph_consistency import HeavenlyGraphConsistencyAudit
from app.services.heavenly_graph_semantics import DEFAULT_RELATION_TYPE_REGISTRY
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import HeavenlyGraphCheckpointNotFound
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(
    branch: str = "branch:main",
    *,
    namespace: str = "siming_heavenly",
    owner: str | None = None,
) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:final-fix",
        session_id="session:final-fix",
        story_branch_id=branch,
        graph_namespace=namespace,
        owner_actor_id=owner,
    )


def _context(
    scope: HeavenlyGraphScope,
    *,
    scopes: tuple[str, ...] = ("public",),
    principal: str = "reader:siming",
    valid_at: int = 10,
    recorded_at: int | None = 200,
) -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal=principal,
        allowed_visibility_scopes=scopes,
        world_id=scope.world_id,
        session_id=scope.session_id,
        story_branch_id=scope.story_branch_id,
        valid_at=valid_at,
        recorded_at=recorded_at,
        policy_revision="policy:v1",
    )


def _metadata(
    *,
    record_kind: str = "fact",
    visibility: str = "public",
    derivation: str = "authority",
    source_ref: str = "authority:event:final-fix",
) -> GraphSemanticMetadata:
    return GraphSemanticMetadata(
        record_kind=record_kind,
        visibility_scope=visibility,
        derivation_kind=derivation,
        source_event_refs=(source_ref,),
        policy_revision="policy:v1",
        scope_digest="scope:final-fix",
    )


def _provenance(
    *,
    source_kind: str = "authority_event",
    source_ref: str = "authority:event:final-fix",
) -> GraphProvenance:
    return GraphProvenance(
        source_kind=source_kind,
        source_ref=source_ref,
        causation_id="cause:final-fix",
        correlation_id="corr:final-fix",
        producer_system="test",
        evidence_refs=[source_ref],
    )


def _node(
    node_id: str,
    *,
    scope: HeavenlyGraphScope | None = None,
    node_type: str = "world_fact",
    source_kind: str = "authority_event",
    metadata: GraphSemanticMetadata | None = None,
    attributes: dict[str, object] | None = None,
    valid_from: int = 1,
    recorded_at: int = 1,
    revision: int = 1,
    supersedes_revision: int | None = None,
) -> HeavenlyGraphNode:
    source_ref = f"authority:{node_id}"
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type=node_type,
        scope=scope or _scope(),
        validity=GraphValidity(valid_from=valid_from),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes=attributes or {},
        provenance=_provenance(source_kind=source_kind, source_ref=source_ref),
        semantic_metadata=metadata or _metadata(source_ref=source_ref),
    )


def _relation(
    relation_id: str,
    source: str,
    target: str,
    *,
    scope: HeavenlyGraphScope | None = None,
    relation_type: str = "caused_by",
    metadata: GraphSemanticMetadata | None = None,
    attributes: dict[str, object] | None = None,
    source_scope: HeavenlyGraphScope | None = None,
    target_scope: HeavenlyGraphScope | None = None,
) -> HeavenlyGraphRelation:
    source_ref = f"authority:{relation_id}"
    return HeavenlyGraphRelation(
        relation_id=relation_id,
        relation_type=relation_type,
        source_node_id=source,
        target_node_id=target,
        scope=scope or _scope(),
        source_scope=source_scope,
        target_scope=target_scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        attributes=attributes or {},
        provenance=_provenance(source_ref=source_ref),
        semantic_metadata=metadata or _metadata(source_ref=source_ref),
    )


def _write(
    graph: object,
    *,
    scope: HeavenlyGraphScope,
    key: str,
    nodes: list[HeavenlyGraphNode] | None = None,
    relations: list[HeavenlyGraphRelation] | None = None,
) -> None:
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id=f"tx:{key}",
            idempotency_key=f"idem:{key}",
            scope=scope,
            nodes=nodes or [],
            relations=relations or [],
        )
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    adapter = (
        InMemoryHeavenlyGraphAdapter()
        if request.param == "memory"
        else SQLiteHeavenlyGraphAdapter(tmp_path / "final-fix.sqlite3")
    )
    yield adapter
    if isinstance(adapter, SQLiteHeavenlyGraphAdapter):
        adapter.close()


def test_sqlite_write_batch_persist_failure_restores_live_and_durable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "write-rollback.sqlite3"
    graph = SQLiteHeavenlyGraphAdapter(path)
    scope = _scope()
    node = _node("fact:failed-write")

    monkeypatch.setattr(graph, "_persist", lambda: (_ for _ in ()).throw(OSError("persist failed")))
    with pytest.raises(OSError, match="persist failed"):
        _write(graph, scope=scope, key="failed-write", nodes=[node])

    assert graph.get_node(node_id=node.node_id, scope=scope, valid_at=10) is None
    assert graph.has_idempotency_key(scope=scope, idempotency_key="idem:failed-write") is False
    assert graph.scope_revision_vector(scope).node_revision == 0
    monkeypatch.setattr(graph, "_persist", type(graph)._persist.__get__(graph))
    graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    assert reopened.get_node(node_id=node.node_id, scope=scope, valid_at=10) is None
    assert reopened.scope_revision_vector(scope).node_revision == 0
    reopened.close()


def test_sqlite_checkpoint_persist_failure_restores_live_and_durable_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "checkpoint-rollback.sqlite3"
    graph = SQLiteHeavenlyGraphAdapter(path)
    scope = _scope()
    _write(graph, scope=scope, key="checkpoint-seed", nodes=[_node("fact:seed")])
    checkpoint_ref = graph._checkpoint_ref("checkpoint:failed", scope)

    monkeypatch.setattr(graph, "_persist", lambda: (_ for _ in ()).throw(OSError("persist failed")))
    with pytest.raises(OSError, match="persist failed"):
        graph.create_checkpoint(
            checkpoint_id="checkpoint:failed",
            scope=scope,
            valid_at=10,
            recorded_at=10,
        )
    with pytest.raises(HeavenlyGraphCheckpointNotFound):
        graph.read_checkpoint(checkpoint_ref)
    monkeypatch.setattr(graph, "_persist", type(graph)._persist.__get__(graph))
    graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    with pytest.raises(HeavenlyGraphCheckpointNotFound):
        reopened.read_checkpoint(checkpoint_ref)
    reopened.close()


@pytest.mark.parametrize(
    "source_kind", ["character_memory", "siming_projection", "runtime_outcome", "authored_seed"]
)
def test_world_fact_authority_rejects_non_owner_provenance(
    graph: object, source_kind: str
) -> None:
    node = _node(f"fact:forged:{source_kind}", source_kind=source_kind)
    with pytest.raises(ValueError, match="canonical owner provenance"):
        _write(graph, scope=node.scope, key=f"forged:{source_kind}", nodes=[node])


@pytest.mark.parametrize("source_kind", ["authority_event", "world_result", "esm_result"])
def test_world_fact_authority_accepts_canonical_owner_provenance(
    graph: object, source_kind: str
) -> None:
    node = _node(f"fact:canonical:{source_kind}", source_kind=source_kind)
    _write(graph, scope=node.scope, key=f"canonical:{source_kind}", nodes=[node])
    assert graph.get_node(node_id=node.node_id, scope=node.scope, valid_at=10) is not None


def test_projection_proposal_and_owned_actor_memory_remain_admissible(graph: object) -> None:
    scope = _scope()
    projection = _node(
        "projection:siming",
        node_type="causal_event",
        source_kind="siming_projection",
        metadata=_metadata(record_kind="projection", derivation="projection"),
    )
    proposal = _node(
        "proposal:siming",
        node_type="policy_candidate",
        source_kind="siming_projection",
        metadata=_metadata(
            record_kind="proposal", visibility="siming_internal", derivation="inference"
        ),
    )
    _write(graph, scope=scope, key="supported-derived", nodes=[projection, proposal])

    actor_scope = _scope(namespace="actor_private", owner="char:b")
    memory = _node(
        "memory:owned",
        scope=actor_scope,
        node_type="actor_memory_ref",
        source_kind="character_memory",
        metadata=_metadata(visibility="actor_private"),
    )
    _write(graph, scope=actor_scope, key="supported-memory", nodes=[memory])
    assert graph.get_node(node_id=memory.node_id, scope=actor_scope, valid_at=10) is not None


def test_public_semantic_paths_drop_relations_with_hidden_endpoints(graph: object) -> None:
    scope = _scope()
    public = _node(
        "fact:public",
        attributes={"turn_id": "turn:hidden-endpoint"},
    )
    hidden = _node(
        "fact:hidden",
        node_type="causal_event",
        metadata=_metadata(visibility="siming_internal"),
    )
    causal = _relation("relation:causal-hidden", public.node_id, hidden.node_id)
    derived = _relation(
        "relation:source-hidden",
        public.node_id,
        hidden.node_id,
        relation_type="derived_from",
        metadata=_metadata(
            record_kind="projection",
            visibility="authority_only",
            derivation="projection",
            source_ref="source:hidden-endpoint",
        ),
    )
    _write(
        graph,
        scope=scope,
        key="public-hidden-endpoint",
        nodes=[public, hidden],
        relations=[causal, derived],
    )
    context = _context(scope, scopes=("public", "authority_only"))
    queries = [
        RelationLookupQuery(context=context, relation_ids=[causal.relation_id]),
        CausalPathQuery(context=context, seed_node_ids=[public.node_id]),
        BehaviorTurnQuery(context=context, turn_id="turn:hidden-endpoint"),
        SourceImpactQuery(context=context, source_ref="source:hidden-endpoint"),
    ]

    for query in queries:
        result = graph.query_semantic(query)
        assert result.relations == []
        assert hidden.node_id not in result.selected_node_refs
        assert result.incomplete_reason == "visibility_denied"


def test_private_semantic_relation_requires_both_endpoints_visible(graph: object) -> None:
    scope = _scope(namespace="actor_private", owner="char:b")
    visible = _node(
        "view:visible",
        scope=scope,
        node_type="actor_view",
        source_kind="character_memory",
        metadata=_metadata(
            record_kind="projection", visibility="actor_private", derivation="projection"
        ),
    )
    hidden = _node(
        "turn:authority-only",
        scope=scope,
        node_type="behavior_turn",
        metadata=_metadata(
            record_kind="projection", visibility="authority_only", derivation="projection"
        ),
    )
    relation = _relation(
        "relation:private-hidden",
        visible.node_id,
        hidden.node_id,
        scope=scope,
        relation_type="contradicts",
        metadata=_metadata(
            record_kind="projection", visibility="actor_private", derivation="projection"
        ),
    )
    _write(
        graph,
        scope=scope,
        key="private-hidden-endpoint",
        nodes=[visible, hidden],
        relations=[relation],
    )
    result = graph.query_semantic(
        RelationLookupQuery(
            context=_context(
                scope,
                scopes=("actor_private",),
                principal="reader:char:b",
            ),
            scope=scope,
            relation_ids=[relation.relation_id],
        )
    )
    assert result.relations == []
    assert result.incomplete_reason == "visibility_denied"


def test_fork_uses_snapshot_vector_and_is_invisible_before_fork_coordinates(
    graph: object,
) -> None:
    production = _scope()
    _write(graph, scope=production, key="fork-seed", nodes=[_node("fact:fork-seed")])
    _write(
        graph,
        scope=production,
        key="fork-future",
        nodes=[_node("fact:future", recorded_at=200)],
    )
    checkpoint = graph.create_checkpoint(
        checkpoint_id="checkpoint:fork-coordinate",
        scope=production,
        valid_at=10,
        recorded_at=100,
    )
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:coordinate",
            fork_valid_at=10,
            fork_recorded_at=100,
            source_revision_vector=checkpoint.source_revision_vector,
        )
    )
    branch = _scope("branch:coordinate")
    assert graph.query_nodes(
        HeavenlyNodeQuery(scope=branch, valid_at=10, recorded_at=50, limit=10)
    ) == []
    assert graph.query_nodes(
        HeavenlyNodeQuery(scope=branch, valid_at=5, recorded_at=100, limit=10)
    ) == []
    assert [
        node.node_id
        for node in graph.query_nodes(
            HeavenlyNodeQuery(scope=branch, valid_at=10, recorded_at=100, limit=10)
        )
    ] == ["fact:fork-seed"]

    before = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(
                production,
                scopes=("public", "authority_only"),
                recorded_at=50,
            ),
        )
    )
    assert before.lifecycle_markers == []
    assert before.right_revision_vector.node_revision == 0
    assert before.right_revision_vector.branch_revision == 0
    after = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(
                production,
                scopes=("public", "authority_only"),
                recorded_at=100,
            ),
        )
    )
    fork = next(marker for marker in after.lifecycle_markers if marker.operation == "fork")
    assert fork.recorded_at == 100
    assert fork.source_revision_vector == checkpoint.source_revision_vector
    assert fork.revision_vector.node_revision == 1
    assert fork.revision_vector.branch_revision == 1


@pytest.mark.parametrize("operation", ["close_node", "discard", "admit"])
def test_lifecycle_markers_use_requested_coordinates_and_post_write_vectors(
    graph: object, operation: str
) -> None:
    production = _scope()
    node = _node(f"fact:lifecycle:{operation}")
    _write(graph, scope=production, key=f"lifecycle-seed:{operation}", nodes=[node])
    branch_id = f"branch:lifecycle:{operation}"
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id=branch_id,
            fork_valid_at=10,
            fork_recorded_at=100,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope(branch_id)
    request = GraphBranchLifecycleRequest(
        branch_scope=branch,
        operation=operation,
        node_id=node.node_id if operation == "close_node" else None,
        target_branch_id="branch:lifecycle:admitted" if operation == "admit" else None,
        valid_at=20,
        recorded_at=150,
        expected_revision_vector=graph.scope_revision_vector(branch),
    )
    graph.lifecycle_branch(request)
    observed_scope = (
        _scope("branch:lifecycle:admitted") if operation == "admit" else branch
    )
    before = graph.query_nodes(
        HeavenlyNodeQuery(
            scope=observed_scope, valid_at=20, recorded_at=149, limit=10
        )
    )
    after = graph.query_nodes(
        HeavenlyNodeQuery(
            scope=observed_scope, valid_at=20, recorded_at=150, limit=10
        )
    )
    if operation == "admit":
        assert before == []
        assert [item.node_id for item in after] == [node.node_id]
    else:
        assert [item.node_id for item in before] == [node.node_id]
        assert after == []

    audit = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=observed_scope,
            reader_context=_context(
                production,
                scopes=("public", "authority_only"),
                valid_at=20,
                recorded_at=150,
            ),
        )
    )
    marker = next(
        item
        for item in audit.lifecycle_markers
        if item.operation == operation
        and (operation != "admit" or item.branch_scope == observed_scope)
    )
    assert marker.recorded_at == 150
    assert marker.revision_vector.branch_revision == 2
    assert marker.revision_vector.node_revision == (
        2 if operation == "close_node" else 1
    )
    assert marker.revision_vector.relation_revision == (
        1 if operation == "close_node" else 0
    )


@pytest.mark.parametrize("correction_kind", ["corrected", "retracted", "redacted"])
def test_fork_and_admit_preserve_complete_correction_history(
    graph: object, correction_kind: str
) -> None:
    production = _scope()
    source = _node(f"fact:history:{correction_kind}", recorded_at=10)
    _write(graph, scope=production, key=f"history-seed:{correction_kind}", nodes=[source])
    graph.correct(
        GraphCorrectionRequest(
            target_kind="node",
            target_id=source.node_id,
            target_revision=1,
            correction_kind=correction_kind,
            source_refs=[f"authority:correction:{correction_kind}"],
            semantic_metadata=source.semantic_metadata,
            scope=production,
        )
    )
    branch_id = f"branch:history:{correction_kind}"
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id=branch_id,
            fork_valid_at=10,
            fork_recorded_at=20,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope(branch_id)
    branch_context = _context(
        branch,
        scopes=("public", "authority_only"),
        recorded_at=20,
    )
    branch_audit = HeavenlyGraphConsistencyAudit(graph).audit(branch, branch_context)
    assert branch_audit.errors == []
    assert branch_audit.checked_node_revisions == 2
    checkpoint = graph.create_checkpoint(
        checkpoint_id=f"checkpoint:history:{correction_kind}",
        scope=branch,
        valid_at=10,
        recorded_at=20,
    )
    assert [
        item.revision for item in graph.read_checkpoint(checkpoint.checkpoint_ref).replay_nodes
    ] == [1, 2]

    target = _scope(f"branch:history:admitted:{correction_kind}")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="admit",
            target_branch_id=target.story_branch_id,
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    target_audit = HeavenlyGraphConsistencyAudit(graph).audit(
        target,
        _context(target, scopes=("public", "authority_only"), recorded_at=20),
    )
    assert target_audit.errors == []
    assert target_audit.checked_node_revisions == 2


def test_conflict_query_returns_every_relevant_revision(graph: object) -> None:
    scope = _scope()
    attributes = {"subject_ref": "world:claim", "property_key": "state"}
    first = _node("claim:revisioned", attributes=attributes, recorded_at=10)
    second = _node(
        "claim:revisioned",
        attributes=attributes,
        recorded_at=20,
        revision=2,
        supersedes_revision=1,
    )
    _write(graph, scope=scope, key="conflict-v1", nodes=[first])
    _write(graph, scope=scope, key="conflict-v2", nodes=[second])
    result = graph.query_semantic(
        ConflictSetQuery(
            context=_context(scope, recorded_at=20),
            subject_ref="world:claim",
            property_key="state",
        )
    )
    assert [node.revision for node in result.nodes] == [1, 2]


def test_branch_diff_uses_only_bounded_adapter_reads(
    graph: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = _scope()
    _write(
        graph,
        scope=production,
        key="bounded-diff-seed",
        nodes=[_node("fact:diff:a"), _node("fact:diff:b")],
    )
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:bounded-diff",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:bounded-diff")
    _write(
        graph,
        scope=branch,
        key="bounded-diff-extra",
        nodes=[_node("fact:diff:c", scope=branch)],
    )
    original_nodes = graph.query_nodes
    original_relations = graph.query_relations

    def checked_nodes(query: object):
        assert query.limit is not None
        return original_nodes(query)

    def checked_relations(query: object):
        assert query.limit is not None
        return original_relations(query)

    monkeypatch.setattr(graph, "query_nodes", checked_nodes)
    monkeypatch.setattr(graph, "query_relations", checked_relations)
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(
                production,
                scopes=("public", "authority_only"),
                recorded_at=20,
            ),
            limits={"node_limit": 1, "relation_limit": 1, "marker_limit": 1},
        )
    )
    assert result.truncated is True


def test_revision_vectors_include_only_reader_visible_writes(graph: object) -> None:
    public_scope = _scope()
    public = _node("fact:vector-public")
    hidden = _node(
        "fact:vector-hidden",
        node_type="causal_event",
        metadata=_metadata(visibility="siming_internal"),
    )
    _write(
        graph,
        scope=public_scope,
        key="public-vector",
        nodes=[public, hidden],
    )
    public_result = graph.query_semantic(
        NodeLookupQuery(context=_context(public_scope), limit=10)
    )
    assert [item.node_id for item in public_result.nodes] == [public.node_id]
    assert public_result.revision_vector.node_revision == 1

    private_scope = _scope(namespace="actor_private", owner="char:b")
    private = _node(
        "view:vector-private",
        scope=private_scope,
        node_type="actor_view",
        source_kind="character_memory",
        metadata=_metadata(
            record_kind="projection", visibility="actor_private", derivation="projection"
        ),
    )
    authority_hidden = _node(
        "turn:vector-hidden",
        scope=private_scope,
        node_type="behavior_turn",
        metadata=_metadata(
            record_kind="projection", visibility="authority_only", derivation="projection"
        ),
    )
    _write(
        graph,
        scope=private_scope,
        key="private-vector",
        nodes=[private, authority_hidden],
    )
    private_result = graph.query_semantic(
        NodeLookupQuery(
            context=_context(
                private_scope,
                scopes=("actor_private",),
                principal="reader:char:b",
            ),
            scope=private_scope,
            limit=10,
        )
    )
    assert [item.node_id for item in private_result.nodes] == [private.node_id]
    assert private_result.revision_vector.node_revision == 1


def test_v1_registry_accepts_cross_namespace_relations_with_endpoint_scopes() -> None:
    DEFAULT_RELATION_TYPE_REGISTRY.validate(
        relation_type="requires_capability",
        source_namespace="siming_heavenly",
        target_namespace="resource_capability",
        record_kind="projection",
        visibility_scope="siming_internal",
    )


def test_adapter_accepts_cross_namespace_endpoint_with_explicit_scopes(
    graph: object,
) -> None:
    siming_scope = _scope()
    resource_scope = _scope(namespace="resource_capability")
    story = _node("story:needs-capability", node_type="story_node_instance")
    capability = _node(
        "capability:oven",
        scope=resource_scope,
        node_type="resource_capability",
    )
    _write(graph, scope=siming_scope, key="cross-story", nodes=[story])
    _write(graph, scope=resource_scope, key="cross-capability", nodes=[capability])
    relation = _relation(
        "relation:cross-capability",
        story.node_id,
        capability.node_id,
        relation_type="requires_capability",
        metadata=_metadata(
            record_kind="projection", visibility="siming_internal", derivation="projection"
        ),
        source_scope=siming_scope,
        target_scope=resource_scope,
    )
    _write(
        graph,
        scope=siming_scope,
        key="cross-capability-relation",
        relations=[relation],
    )
