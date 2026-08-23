from __future__ import annotations

from pathlib import Path

import pytest

from app.models.siming_heavenly_graph import (
    GraphBranchDiffLimits,
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


def _scope(branch: str = "branch:main") -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:final-fix-4",
        session_id="session:final-fix-4",
        story_branch_id=branch,
        graph_namespace="siming_heavenly",
    )


def _context(scope: HeavenlyGraphScope) -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal="reader:siming",
        allowed_visibility_scopes=("public", "authority_only"),
        world_id=scope.world_id,
        session_id=scope.session_id,
        story_branch_id=scope.story_branch_id,
        valid_at=10,
        recorded_at=100,
        policy_revision="policy:v1",
    )


def _node(node_id: str, scope: HeavenlyGraphScope) -> HeavenlyGraphNode:
    source_ref = f"authority:{node_id}"
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="world_fact",
        scope=scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        attributes={},
        provenance={
            "source_kind": "authority_event",
            "source_ref": source_ref,
            "causation_id": f"cause:{node_id}",
            "correlation_id": "corr:final-fix-4",
            "producer_system": "test",
        },
        semantic_metadata=GraphSemanticMetadata(
            source_event_refs=(source_ref,),
            policy_revision="policy:v1",
            scope_digest="scope:final-fix-4",
        ),
    )


def _write(graph: object, scope: HeavenlyGraphScope) -> None:
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:wave4-seed",
            idempotency_key="idem:wave4-seed",
            scope=scope,
            nodes=[_node(f"fact:wave4:{index}", scope) for index in range(3)],
        )
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    adapter = (
        InMemoryHeavenlyGraphAdapter()
        if request.param == "memory"
        else SQLiteHeavenlyGraphAdapter(tmp_path / "final-fix-wave-4.sqlite3")
    )
    yield adapter
    if isinstance(adapter, SQLiteHeavenlyGraphAdapter):
        adapter.close()


def test_same_scope_branch_diff_reuses_one_bounded_marker_window(
    graph: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = _scope()
    _write(graph, production)
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:wave4",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:wave4")
    for index in range(3):
        graph.lifecycle_branch(
            GraphBranchLifecycleRequest(
                branch_scope=branch,
                operation="close_node",
                node_id=f"fact:wave4:{index}",
                valid_at=10,
                recorded_at=20 + index,
                expected_revision_vector=graph.scope_revision_vector(branch),
            )
        )

    class SpyMarkers(list[object]):
        def __init__(self, values: list[object], maximum_reads: int) -> None:
            super().__init__(values)
            self.maximum_reads = maximum_reads
            self.reads = 0

        def __getitem__(self, index: int):
            self.reads += 1
            if self.reads > self.maximum_reads:
                raise AssertionError("same-scope marker stream inspected more than once")
            return super().__getitem__(index)

    key = graph._scope_key(branch)
    markers = SpyMarkers(graph._branch_markers[key], maximum_reads=4)
    graph._branch_markers[key] = markers
    monkeypatch.setattr(
        graph,
        "_scope_revision_vector",
        lambda *args, **kwargs: GraphRevisionVector(),
    )
    monkeypatch.setattr(graph, "_branch_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(graph, "_is_node_closed", lambda *args, **kwargs: False)
    monkeypatch.setattr(graph, "_is_branch_discarded", lambda *args, **kwargs: False)

    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=branch,
            right_scope=branch,
            reader_context=_context(branch),
            limits=GraphBranchDiffLimits(
                node_limit=100,
                relation_limit=100,
                marker_limit=8,
            ),
        )
    )

    assert markers.reads == 4
    assert len(result.lifecycle_markers) == 4
    assert len({marker.marker_id for marker in result.lifecycle_markers}) == 4
    assert result.truncated is False
