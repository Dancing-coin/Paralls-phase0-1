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
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app.services.siming_heavenly_graph_port import HeavenlyGraphRevisionConflict


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
