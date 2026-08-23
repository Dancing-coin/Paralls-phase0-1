from pathlib import Path

import pytest

from app.models.siming_heavenly_graph import (
    GraphBranchDiffQuery,
    GraphBranchForkRequest,
    GraphBranchLifecycleRequest,
    GraphReaderContext,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
    HeavenlyNodeQuery,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphReferentialIntegrityError,
    HeavenlyGraphRevisionConflict,
)


def _scope(branch: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:branch",
        session_id="session:branch",
        story_branch_id=branch,
        graph_namespace="siming_heavenly",
    )


def _context(branch: str = "branch:main") -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal="reader:siming",
        allowed_visibility_scopes=("public", "authority_only", "branch_only"),
        world_id="world:branch",
        session_id="session:branch",
        story_branch_id=branch,
        valid_at=10,
        policy_revision="policy:v1",
    )


def _node(node_id: str, *, branch: str = "branch:main", value: str = "v1") -> HeavenlyGraphNode:
    scope = _scope(branch)
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="story_node_instance",
        scope=scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        attributes={"value": value},
        provenance={
            "source_kind": "authority_event",
            "source_ref": f"authority:{node_id}",
            "causation_id": f"cause:{node_id}",
            "correlation_id": "corr:branch",
            "producer_system": "test",
        },
        semantic_metadata=GraphSemanticMetadata(
            visibility_scope="public", policy_revision="policy:v1"
        ),
    )


def _write(graph: object, node: HeavenlyGraphNode) -> None:
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id=f"tx:{node.node_id}",
            idempotency_key=f"idem:{node.node_id}",
            scope=node.scope,
            nodes=[node],
        )
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "memory":
        return InMemoryHeavenlyGraphAdapter()
    return SQLiteHeavenlyGraphAdapter(tmp_path / "branch.sqlite3")


def _nodes(graph: object, scope: HeavenlyGraphScope) -> list[str]:
    return [
        item.node_id
        for item in graph.query_nodes(
            __import__("app.models.siming_heavenly_graph", fromlist=["HeavenlyNodeQuery"]).HeavenlyNodeQuery(
                scope=scope, valid_at=10, limit=None
            )
        )
    ]


def test_fork_is_snapshot_isolated_and_branch_only_writes_do_not_contaminate_production(graph: object) -> None:
    production = _scope()
    _write(graph, _node("story:seed"))
    source_vector = graph.scope_revision_vector(production)
    result = graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:preview",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=source_vector,
        )
    )
    branch = _scope("branch:preview")
    assert result.applied is True
    assert _nodes(graph, branch) == ["story:seed"]

    _write(graph, _node("story:branch-only", branch="branch:preview"))
    assert _nodes(graph, production) == ["story:seed"]
    assert _nodes(graph, branch) == ["story:branch-only", "story:seed"]


def test_fork_uses_requested_non_default_temporal_coordinates(graph: object) -> None:
    production = _scope()
    source = _node("late-seed").model_copy(
        update={
            "validity": GraphValidity(valid_from=100),
            "recorded_at": 100,
        }
    )
    _write(graph, source)
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:late-fork",
            fork_valid_at=100,
            fork_recorded_at=100,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    assert [
        node.node_id
        for node in graph.query_nodes(
            HeavenlyNodeQuery(
                scope=_scope("branch:late-fork"), valid_at=100, limit=None
            )
        )
    ] == ["late-seed"]


def test_branch_diff_is_deterministic_and_reports_added_removed_changed(graph: object) -> None:
    production = _scope()
    _write(graph, _node("same", value="before"))
    _write(graph, _node("left-only"))
    vector = graph.scope_revision_vector(production)
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:diff",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=vector,
        )
    )
    branch = _scope("branch:diff")
    _write(graph, _node("right-only", branch="branch:diff"))
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="left-only",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    changed = _node("same", branch="branch:diff", value="after").model_copy(
        update={"revision": 2, "supersedes_revision": 1, "recorded_at": 11}
    )
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:changed",
            idempotency_key="idem:changed",
            scope=branch,
            nodes=[changed],
        )
    )
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(),
            limits={"node_limit": 10, "relation_limit": 10, "marker_limit": 10},
        )
    )
    assert [node.node_id for node in result.added_nodes] == ["right-only"]
    assert [node.node_id for node in result.removed_nodes] == ["left-only"]
    assert [node.node_id for node in result.changed_nodes] == ["same"]


def test_pristine_fork_has_no_semantic_diff_after_scope_normalization(graph: object) -> None:
    production = _scope()
    _write(graph, _node("same", value="unchanged"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:pristine",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=_scope("branch:pristine"),
            reader_context=_context(),
        )
    )
    assert result.added_nodes == []
    assert result.removed_nodes == []
    assert result.changed_nodes == []
    assert result.added_relations == []
    assert result.removed_relations == []
    assert result.changed_relations == []


def test_public_branch_diff_does_not_leak_lifecycle_markers(graph: object) -> None:
    production = _scope()
    _write(graph, _node("close-me"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:public-read",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:public-read")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="close-me",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    public_context = _context()
    public_context = public_context.model_copy(
        update={"allowed_visibility_scopes": ("public",)}
    )
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=public_context,
        )
    )
    assert result.lifecycle_markers == []


def test_policy_mismatched_authority_reader_does_not_receive_lifecycle_markers(
    graph: object,
) -> None:
    production = _scope()
    _write(graph, _node("policy-close"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:policy-read",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:policy-read")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="policy-close",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context().model_copy(update={"policy_revision": "policy:v2"}),
        )
    )
    assert result.lifecycle_markers == []


def test_historical_diff_before_lifecycle_marker_hides_future_marker(graph: object) -> None:
    production = _scope()
    _write(graph, _node("diff-history"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:diff-history",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:diff-history")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="diff-history",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    context = _context().model_copy(update={"recorded_at": 1})
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=context,
        )
    )
    assert result.lifecycle_markers == []


def test_branch_diff_hides_lifecycle_markers_after_reader_recorded_at(
    graph: object,
) -> None:
    production = _scope()
    _write(graph, _node("recorded-close"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:recorded-close",
            fork_valid_at=10,
            fork_recorded_at=1,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:recorded-close")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="recorded-close",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    before_close = _context().model_copy(update={"recorded_at": 1})
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=before_close,
        )
    )
    assert [marker.operation for marker in result.lifecycle_markers] == ["fork"]
    after_close = _context().model_copy(update={"recorded_at": 2})
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=after_close,
        )
    )
    assert any(marker.operation == "close_node" for marker in result.lifecycle_markers)


@pytest.mark.parametrize("visibility_scope", ["public", "branch_only"])
def test_unknown_branch_scope_rejects_all_direct_writes(
    graph: object, visibility_scope: str
) -> None:
    unknown_branch = _node("unknown", branch="branch:unknown").model_copy(
        update={
            "semantic_metadata": GraphSemanticMetadata(
                visibility_scope=visibility_scope, policy_revision="policy:v1"
            )
        }
    )
    with pytest.raises(ValueError):
        _write(graph, unknown_branch)


def test_known_production_main_scope_still_accepts_direct_writes(
    graph: object,
) -> None:
    _write(graph, _node("production-main", branch="branch:main"))
    assert _nodes(graph, _scope()) == ["production-main"]


@pytest.mark.parametrize("terminal_operation", ["discard", "admit"])
def test_terminal_branch_rejects_new_writes(
    graph: object, terminal_operation: str
) -> None:
    production = _scope()
    _write(graph, _node("source"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id=f"branch:terminal-{terminal_operation}",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope(f"branch:terminal-{terminal_operation}")
    if terminal_operation == "discard":
        graph.lifecycle_branch(
            GraphBranchLifecycleRequest(
                branch_scope=branch,
                operation="discard",
                expected_revision_vector=graph.scope_revision_vector(branch),
            )
        )
        target = branch
    else:
        graph.lifecycle_branch(
            GraphBranchLifecycleRequest(
                branch_scope=branch,
                operation="admit",
                target_branch_id="branch:admitted-terminal",
                expected_revision_vector=graph.scope_revision_vector(branch),
            )
        )
        target = branch
    with pytest.raises(ValueError):
        _write(graph, _node("after-terminal", branch=target.story_branch_id))


def test_admission_preserves_closed_node_tombstone_and_rejects_resurrection(
    graph: object,
) -> None:
    production = _scope()
    _write(graph, _node("closed-source"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:closed-preview",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    preview = _scope("branch:closed-preview")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=preview,
            operation="close_node",
            node_id="closed-source",
            expected_revision_vector=graph.scope_revision_vector(preview),
        )
    )
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=preview,
            operation="admit",
            target_branch_id="branch:closed-admitted",
            expected_revision_vector=graph.scope_revision_vector(preview),
        )
    )
    with pytest.raises(
        (ValueError, HeavenlyGraphRevisionConflict, HeavenlyGraphReferentialIntegrityError)
    ):
        _write(graph, _node("closed-source", branch="branch:closed-admitted"))


def test_admission_keeps_a_target_branch_audit_marker(graph: object) -> None:
    production = _scope()
    _write(graph, _node("admit-audit"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:admit-source",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    source = _scope("branch:admit-source")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=source,
            operation="admit",
            target_branch_id="branch:admit-target",
            expected_revision_vector=graph.scope_revision_vector(source),
        )
    )
    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=_scope("branch:admit-target"),
            reader_context=_context(),
        )
    )
    assert any(marker.operation == "admit" for marker in result.lifecycle_markers)


def test_admission_marker_source_and_target_streams_are_coherent(
    graph: object,
) -> None:
    production = _scope()
    _write(graph, _node("admit-node-a"))
    _write(graph, _node("admit-node-b"))
    production_vector = graph.scope_revision_vector(production)
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:coherent-source",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=production_vector,
        )
    )
    source = _scope("branch:coherent-source")
    source_vector = graph.scope_revision_vector(source)
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=source,
            operation="admit",
            target_branch_id="branch:coherent-target",
            expected_revision_vector=source_vector,
        )
    )
    target = _scope("branch:coherent-target")
    target_vector = graph.scope_revision_vector(target)
    assert target_vector.node_revision == 2
    assert target_vector.relation_revision == 0
    target_audit = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=target,
            reader_context=_context(),
        )
    )
    target_admit = next(
        marker for marker in target_audit.lifecycle_markers
        if marker.operation == "admit"
    )
    assert target_admit.source_scope == source
    assert target_admit.source_revision_vector == source_vector
    assert target_admit.revision_vector.node_revision == 2
    assert target_admit.revision_vector.relation_revision == 0
    source_audit = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=source,
            reader_context=_context(),
        )
    )
    source_admit = next(
        marker for marker in source_audit.lifecycle_markers
        if marker.operation == "admit"
    )
    assert source_admit.source_scope == production
    assert source_admit.source_revision_vector == production_vector


def test_fork_rejects_terminal_source_branch(graph: object) -> None:
    production = _scope()
    _write(graph, _node("source"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:closed-source",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    source = _scope("branch:closed-source")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=source,
            operation="discard",
            expected_revision_vector=graph.scope_revision_vector(source),
        )
    )
    with pytest.raises(ValueError):
        graph.fork_branch(
            GraphBranchForkRequest(
                source_scope=source,
                target_branch_id="branch:resurrected",
                fork_valid_at=10,
                fork_recorded_at=10,
                source_revision_vector=graph.scope_revision_vector(source),
            )
        )


def test_fork_propagates_permanent_close_state(graph: object) -> None:
    production = _scope()
    _write(graph, _node("fork-closed"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:closed-parent",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    parent = _scope("branch:closed-parent")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=parent,
            operation="close_node",
            node_id="fork-closed",
            expected_revision_vector=graph.scope_revision_vector(parent),
        )
    )
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=parent,
            target_branch_id="branch:closed-child",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(parent),
        )
    )
    with pytest.raises((ValueError, HeavenlyGraphRevisionConflict)):
        _write(graph, _node("fork-closed", branch="branch:closed-child"))


def test_direct_lifecycle_marker_records_cannot_bypass_authority(graph: object) -> None:
    branch = _scope("branch:unadmitted")
    marker = _node("branch:closed:forged", branch=branch.story_branch_id).model_copy(
        update={"node_type": "branch_marker"}
    )
    with pytest.raises(ValueError):
        _write(graph, marker)


def test_historical_read_before_close_keeps_original_node_visible(graph: object) -> None:
    production = _scope()
    _write(graph, _node("historical"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:historical-close",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:historical-close")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="historical",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    assert graph.query_nodes(
        HeavenlyNodeQuery(scope=branch, valid_at=10, recorded_at=1, limit=None)
    )
    assert graph.query_nodes(
        HeavenlyNodeQuery(scope=branch, valid_at=10, recorded_at=2, limit=None)
    ) == []


def test_relation_cannot_bypass_permanent_close_tombstone(graph: object) -> None:
    production = _scope()
    _write(graph, _node("closed-endpoint"))
    _write(graph, _node("other-endpoint"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:relation-close",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:relation-close")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="closed-endpoint",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    relation = HeavenlyGraphRelation(
        relation_id="relation:after-close",
        relation_type="caused_by",
        source_node_id="other-endpoint",
        target_node_id="closed-endpoint",
        scope=branch,
        validity=GraphValidity(valid_from=1),
        recorded_at=3,
        revision=1,
        provenance={
            "source_kind": "authority_event",
            "source_ref": "authority:relation:after-close",
            "causation_id": "cause:relation:after-close",
            "correlation_id": "corr:branch",
            "producer_system": "test",
        },
        semantic_metadata=GraphSemanticMetadata(policy_revision="policy:v1"),
    )
    with pytest.raises(
        (ValueError, HeavenlyGraphRevisionConflict, HeavenlyGraphReferentialIntegrityError)
    ):
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="tx:relation-after-close",
                idempotency_key="idem:relation-after-close",
                scope=branch,
                relations=[relation],
            )
        )


def test_historical_read_before_discard_keeps_branch_snapshot_visible(graph: object) -> None:
    production = _scope()
    _write(graph, _node("discard-history"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:discard-history",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:discard-history")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="discard",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    assert graph.query_nodes(
        HeavenlyNodeQuery(scope=branch, valid_at=10, recorded_at=1, limit=None)
    )
    assert graph.query_nodes(
        HeavenlyNodeQuery(scope=branch, valid_at=10, recorded_at=2, limit=None)
    ) == []


def test_close_node_is_permanent_and_appends_a_close_marker(graph: object) -> None:
    production = _scope()
    _write(graph, _node("story:closeable"))
    vector = graph.scope_revision_vector(production)
    branch_result = graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:close",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=vector,
        )
    )
    branch = _scope("branch:close")
    closed = graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="story:closeable",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    assert closed.applied is True
    assert _nodes(graph, branch) == []
    assert graph.get_node(node_id="story:closeable", scope=branch, valid_at=10) is None
    markers = graph.query_semantic(
        __import__("app.models.siming_heavenly_graph", fromlist=["RelationLookupQuery"]).RelationLookupQuery(
            context=_context("branch:close"), relation_types=["closes_branch_node"]
        )
    )
    assert len(markers.relations) == 1
    with pytest.raises(HeavenlyGraphRevisionConflict):
        graph.write_batch(
            HeavenlyGraphWriteBatch(
                transaction_id="tx:resurrect",
                idempotency_key="idem:resurrect",
                scope=branch,
                nodes=[_node("story:closeable", branch="branch:close")],
            )
        )


def test_discard_hides_branch_records_but_does_not_delete_audit_history(graph: object) -> None:
    production = _scope()
    _write(graph, _node("story:discard"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:discard",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:discard")
    discarded = graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="discard",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    assert discarded.applied is True
    assert _nodes(graph, branch) == []
    audit = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(),
            limits={"node_limit": 10, "relation_limit": 10, "marker_limit": 10},
        )
    )
    assert any(marker.operation == "discard" for marker in audit.lifecycle_markers)


def test_fork_rejects_source_vector_mismatch_without_writes(graph: object) -> None:
    production = _scope()
    _write(graph, _node("source"))
    with pytest.raises(HeavenlyGraphRevisionConflict):
        graph.fork_branch(
            GraphBranchForkRequest(
                source_scope=production,
                target_branch_id="branch:stale",
                fork_valid_at=10,
                fork_recorded_at=10,
                source_revision_vector=GraphRevisionVector(node_revision=0),
            )
        )
    assert _nodes(graph, _scope("branch:stale")) == []


def test_discarded_branch_cannot_be_resurrected_or_admitted(graph: object) -> None:
    production = _scope()
    _write(graph, _node("source"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:dead",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:dead")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="discard",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    with pytest.raises(ValueError):
        graph.lifecycle_branch(
            GraphBranchLifecycleRequest(
                branch_scope=branch,
                operation="admit",
                target_branch_id="branch:admitted",
                expected_revision_vector=graph.scope_revision_vector(branch),
            )
        )


def test_admit_rejects_a_branch_when_its_fork_source_vector_is_stale(graph: object) -> None:
    production = _scope()
    _write(graph, _node("source"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:stale-admit",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    _write(graph, _node("production:later"))
    branch = _scope("branch:stale-admit")
    with pytest.raises(HeavenlyGraphRevisionConflict):
        graph.lifecycle_branch(
            GraphBranchLifecycleRequest(
                branch_scope=branch,
                operation="admit",
                target_branch_id="branch:admitted",
                expected_revision_vector=graph.scope_revision_vector(branch),
            )
    )
    assert _nodes(graph, _scope("branch:admitted")) == []


def test_sqlite_restores_discarded_branch_state(tmp_path: Path) -> None:
    path = tmp_path / "branch-restart.sqlite3"
    graph = SQLiteHeavenlyGraphAdapter(path)
    production = _scope()
    _write(graph, _node("source"))
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:restart",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:restart")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="discard",
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    graph.close()

    reopened = SQLiteHeavenlyGraphAdapter(path)
    assert _nodes(reopened, branch) == []
    audit = reopened.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(),
        )
    )
    reopened.close()
    assert any(marker.operation == "discard" for marker in audit.lifecycle_markers)
