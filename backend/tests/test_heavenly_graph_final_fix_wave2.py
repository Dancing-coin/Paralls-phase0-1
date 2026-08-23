from pathlib import Path

import pytest

from app.models.siming_heavenly_graph import (
    ConflictSetQuery,
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
    RelationLookupQuery,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(branch: str = "branch:main", *, owner: str | None = None) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:final-fix-2",
        session_id="session:final-fix-2",
        story_branch_id=branch,
        graph_namespace="actor_private" if owner else "siming_heavenly",
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


def _node(
    node_id: str,
    *,
    scope: HeavenlyGraphScope | None = None,
    node_type: str = "world_fact",
    metadata: GraphSemanticMetadata | None = None,
    attributes: dict[str, object] | None = None,
    recorded_at: int = 1,
    revision: int = 1,
    supersedes_revision: int | None = None,
) -> HeavenlyGraphNode:
    source_ref = f"authority:{node_id}"
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type=node_type,
        scope=scope or _scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=recorded_at,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes=attributes or {},
        provenance={
            "source_kind": "authority_event",
            "source_ref": source_ref,
            "causation_id": f"cause:{node_id}",
            "correlation_id": "corr:final-fix-2",
            "producer_system": "test",
            "evidence_refs": [source_ref],
        },
        semantic_metadata=metadata
        or GraphSemanticMetadata(
            source_event_refs=(source_ref,),
            policy_revision="policy:v1",
            scope_digest="scope:final-fix-2",
        ),
    )


def _write(
    graph: object,
    *,
    scope: HeavenlyGraphScope,
    key: str,
    nodes: list[HeavenlyGraphNode],
) -> None:
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id=f"tx:{key}",
            idempotency_key=f"idem:{key}",
            scope=scope,
            nodes=nodes,
        )
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    adapter = (
        InMemoryHeavenlyGraphAdapter()
        if request.param == "memory"
        else SQLiteHeavenlyGraphAdapter(tmp_path / "final-fix-wave-2.sqlite3")
    )
    yield adapter
    if isinstance(adapter, SQLiteHeavenlyGraphAdapter):
        adapter.close()


def test_close_marker_never_leaks_hidden_target_to_authority_reader(graph: object) -> None:
    production = _scope()
    _write(graph, scope=production, key="close-source", nodes=[_node("fact:closeable")])
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:wave2-close",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:wave2-close")
    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="fact:closeable",
            valid_at=10,
            recorded_at=20,
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )

    result = graph.query_semantic(
        RelationLookupQuery(
            context=_context(
                branch,
                scopes=("public", "authority_only"),
                recorded_at=20,
            ),
            relation_types=["closes_branch_node"],
        )
    )
    assert result.relations == []
    assert result.incomplete_reason == "visibility_denied"


def test_conflict_history_honors_fork_close_and_discard_coordinates(graph: object) -> None:
    production = _scope()
    attributes = {"subject_ref": "world:claim", "property_key": "state"}
    _write(
        graph,
        scope=production,
        key="claim-v1",
        nodes=[_node("claim:revisioned", attributes=attributes, recorded_at=5)],
    )
    _write(
        graph,
        scope=production,
        key="claim-v2",
        nodes=[
            _node(
                "claim:revisioned",
                attributes=attributes,
                recorded_at=8,
                revision=2,
                supersedes_revision=1,
            )
        ],
    )
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:wave2-conflict",
            fork_valid_at=10,
            fork_recorded_at=50,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:wave2-conflict")

    def read(recorded_at: int):
        return graph.query_semantic(
            ConflictSetQuery(
                context=_context(branch, recorded_at=recorded_at),
                subject_ref="world:claim",
                property_key="state",
            )
        )

    assert read(20).nodes == []
    assert [node.revision for node in read(100).nodes] == [1, 2]

    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="close_node",
            node_id="claim:revisioned",
            valid_at=10,
            recorded_at=120,
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    assert read(130).nodes == []

    graph.lifecycle_branch(
        GraphBranchLifecycleRequest(
            branch_scope=branch,
            operation="discard",
            valid_at=10,
            recorded_at=140,
            expected_revision_vector=graph.scope_revision_vector(branch),
        )
    )
    assert read(150).nodes == []


def test_conflict_history_preserves_reader_privacy(graph: object) -> None:
    scope = _scope(owner="char:b")
    own = _node(
        "claim:own",
        scope=scope,
        node_type="actor_view",
        attributes={"subject_ref": "world:claim", "property_key": "state"},
        metadata=GraphSemanticMetadata(
            record_kind="projection",
            visibility_scope="actor_private",
            derivation_kind="projection",
            policy_revision="policy:v1",
            scope_digest="scope:final-fix-2",
        ),
    )
    hidden = _node(
        "claim:hidden",
        scope=scope,
        node_type="behavior_turn",
        attributes={"subject_ref": "world:claim", "property_key": "state"},
        metadata=GraphSemanticMetadata(
            record_kind="projection",
            visibility_scope="authority_only",
            derivation_kind="projection",
            policy_revision="policy:v1",
            scope_digest="scope:final-fix-2",
        ),
    )
    _write(graph, scope=scope, key="private-claims", nodes=[own, hidden])

    result = graph.query_semantic(
        ConflictSetQuery(
            context=_context(
                scope,
                scopes=("actor_private",),
                principal="reader:char:b",
            ),
            scope=scope,
            subject_ref="world:claim",
            property_key="state",
        )
    )
    assert [node.node_id for node in result.nodes] == ["claim:own"]


def test_diff_branch_marker_reads_are_bounded(
    graph: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = _scope()
    _write(
        graph,
        scope=production,
        key="marker-seed",
        nodes=[_node(f"fact:marker:{index}") for index in range(3)],
    )
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:wave2-markers",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:wave2-markers")
    for index in range(3):
        graph.lifecycle_branch(
            GraphBranchLifecycleRequest(
                branch_scope=branch,
                operation="close_node",
                node_id=f"fact:marker:{index}",
                valid_at=10,
                recorded_at=20 + index,
                expected_revision_vector=graph.scope_revision_vector(branch),
            )
        )

    class BoundedMarkers(list[object]):
        def __init__(self, values: list[object], maximum_reads: int) -> None:
            super().__init__(values)
            self.maximum_reads = maximum_reads
            self.reads = 0

        def __iter__(self):
            for value in super().__iter__():
                self.reads += 1
                if self.reads > self.maximum_reads:
                    raise AssertionError("unbounded lifecycle marker read")
                yield value

        def __getitem__(self, index):
            self.reads += 1
            if self.reads > self.maximum_reads:
                raise AssertionError("marker scan exceeded per-stream bound")
            return super().__getitem__(index)

    key = graph._scope_key(branch)
    bounded = BoundedMarkers(graph._branch_markers[key], maximum_reads=4)
    graph._branch_markers[key] = bounded
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
            left_scope=production,
            right_scope=branch,
            reader_context=_context(
                production,
                scopes=("public", "authority_only"),
                recorded_at=100,
            ),
            limits=GraphBranchDiffLimits(
                node_limit=100,
                relation_limit=100,
                marker_limit=1,
            ),
        )
    )
    assert result.truncated is True
    assert len(result.lifecycle_markers) == 1
    assert bounded.reads == 4


def test_diff_marker_scan_bounds_ineligible_history(
    graph: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    production = _scope()
    _write(graph, scope=production, key="ineligible-seed", nodes=[_node("fact:seed")])
    graph.fork_branch(
        GraphBranchForkRequest(
            source_scope=production,
            target_branch_id="branch:wave3-markers",
            fork_valid_at=10,
            fork_recorded_at=10,
            source_revision_vector=graph.scope_revision_vector(production),
        )
    )
    branch = _scope("branch:wave3-markers")
    key = graph._scope_key(branch)
    stale_markers = [
        graph._branch_markers[key][0].model_copy(
            update={
                "marker_id": f"stale-marker:{index:03d}",
                "policy_revision": "policy:old",
            },
            deep=True,
        )
        for index in range(20)
    ]

    class BoundedMarkers(list[object]):
        def __init__(self, values: list[object], maximum_reads: int) -> None:
            super().__init__(values)
            self.maximum_reads = maximum_reads
            self.reads = 0

        def __iter__(self):
            for value in super().__iter__():
                self.reads += 1
                if self.reads > self.maximum_reads:
                    raise AssertionError("marker scan exceeded per-stream bound")
                yield value

        def __getitem__(self, index):
            self.reads += 1
            if self.reads > self.maximum_reads:
                raise AssertionError("marker scan exceeded per-stream bound")
            return super().__getitem__(index)

    bounded = BoundedMarkers(stale_markers, maximum_reads=4)
    graph._branch_markers[key] = bounded
    monkeypatch.setattr(graph, "_branch_available", lambda *args, **kwargs: True)
    monkeypatch.setattr(graph, "_is_node_closed", lambda *args, **kwargs: False)
    monkeypatch.setattr(graph, "_is_branch_discarded", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        graph,
        "_scope_revision_vector",
        lambda *args, **kwargs: GraphRevisionVector(),
    )

    result = graph.diff_branches(
        GraphBranchDiffQuery(
            left_scope=production,
            right_scope=branch,
            reader_context=_context(
                production,
                scopes=("public", "authority_only"),
                recorded_at=100,
            ),
            limits=GraphBranchDiffLimits(
                node_limit=100,
                relation_limit=100,
                marker_limit=1,
            ),
        )
    )
    assert result.lifecycle_markers == []
    assert result.truncated is True
    assert bounded.reads == 4
