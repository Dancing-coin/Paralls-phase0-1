from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from app.models.siming_heavenly_graph import (
    GraphCorrectionRequest,
    GraphProvenance,
    GraphReaderContext,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphWriteBatch,
)
from app.services.heavenly_graph_consistency import HeavenlyGraphConsistencyAudit
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(*, namespace: str = "siming_heavenly", owner: str | None = None) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:audit",
        session_id="session:audit",
        story_branch_id="branch:main",
        graph_namespace=namespace,
        owner_actor_id=owner,
    )


def _context(*, principal: str = "reader:siming", scopes: tuple[str, ...] = ("public",)) -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal=principal,
        allowed_visibility_scopes=scopes,  # type: ignore[arg-type]
        world_id="world:audit",
        session_id="session:audit",
        story_branch_id="branch:main",
        valid_at=10,
        recorded_at=20,
        policy_revision="policy:v1",
    )


def _metadata(**updates: object) -> GraphSemanticMetadata:
    values: dict[str, object] = {
        "record_kind": "fact",
        "visibility_scope": "public",
        "derivation_kind": "authority",
        "source_event_refs": ("authority:audit:1",),
        "policy_revision": "policy:v1",
        "scope_digest": "scope:audit",
    }
    values.update(updates)
    return GraphSemanticMetadata(**values)


def _provenance(*, source_ref: str = "authority:audit:1") -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref=source_ref,
        causation_id="cause:audit",
        correlation_id="corr:audit",
        producer_system="test",
    )


def _node(
    node_id: str = "fact:one",
    *,
    revision: int = 1,
    supersedes_revision: int | None = None,
    metadata: GraphSemanticMetadata | None = None,
) -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id=node_id,
        node_type="world_fact",
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=revision,
        revision=revision,
        supersedes_revision=supersedes_revision,
        attributes={"secret": "visible-value"},
        provenance=_provenance(),
        semantic_metadata=metadata or _metadata(),
    )


def _relation(
    relation_id: str = "relation:one",
    *,
    source: str = "fact:one",
    target: str = "fact:two",
) -> HeavenlyGraphRelation:
    return HeavenlyGraphRelation(
        relation_id=relation_id,
        relation_type="caused_by",
        source_node_id=source,
        target_node_id=target,
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=3,
        revision=1,
        attributes={"secret": "relation-value"},
        provenance=_provenance(),
        semantic_metadata=_metadata(),
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "sqlite":
        adapter = SQLiteHeavenlyGraphAdapter(tmp_path / "audit.sqlite3")
        yield adapter
        adapter.close()
        return
    yield InMemoryHeavenlyGraphAdapter()


def _write_valid_graph(graph: object) -> None:
    scope = _scope()
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:audit:valid",
            idempotency_key="idem:audit:valid",
            scope=scope,
            nodes=[_node("fact:one"), _node("fact:two")],
            relations=[_relation()],
        )
    )


def _inject_invalid_fixture(graph: object, *, kind: str) -> None:
    """Test-only bypass: production admission must reject every fixture below."""

    scope = _scope()
    key = graph._scope_key(scope)
    if kind == "orphan_relation":
        graph._relations[(key, "relation:orphan")] = [_relation("relation:orphan", target="fact:missing")]
    elif kind == "revision_chain":
        malformed = _node("fact:revision", revision=1).model_copy(deep=True)
        malformed.revision = 3
        malformed.supersedes_revision = 1
        graph._nodes[(key, malformed.node_id)] = [malformed]
    elif kind == "provenance":
        malformed = _node("fact:provenance").model_copy(deep=True)
        malformed.provenance = GraphProvenance.model_construct(
            source_kind="authority_event",
            source_ref="",
            causation_id="",
            correlation_id="",
            producer_system="",
            evidence_refs=[],
            source_ref_lineage=[],
        )
        graph._nodes[(key, malformed.node_id)] = [malformed]
    elif kind == "scope":
        malformed = _node("fact:scope").model_copy(
            update={"scope": _scope().model_copy(update={"room_id": "room:other"})},
            deep=True,
        )
        graph._nodes[(key, malformed.node_id)] = [malformed]
    elif kind == "semantic":
        malformed = _node("fact:semantic").model_copy(
            update={"node_type": "unknown_semantic_type"}, deep=True
        )
        graph._nodes[(key, malformed.node_id)] = [malformed]
    elif kind == "correction":
        predecessor = _node("fact:correction")
        malformed = _node("fact:correction", revision=2, supersedes_revision=1).model_copy(
            update={
                "semantic_metadata": _metadata(derivation_kind="correction"),
                "attributes": {
                    "correction_target_id": "fact:wrong",
                    "correction_target_revision": 1,
                    "correction_source_refs": [],
                },
            },
            deep=True,
        )
        graph._nodes[(key, malformed.node_id)] = [predecessor, malformed]
    else:  # pragma: no cover - fixture names are parametrized below.
        raise AssertionError(f"unknown invalid fixture {kind}")


def test_valid_graph_has_no_consistency_errors(graph: object) -> None:
    _write_valid_graph(graph)

    report = HeavenlyGraphConsistencyAudit(graph).audit(_scope(), _context())

    assert report.errors == []
    assert report.checked_node_revisions == 2
    assert report.checked_relation_revisions == 1


def test_adapter_exposes_the_read_only_consistency_audit(graph: object) -> None:
    _write_valid_graph(graph)

    report = graph.audit_consistency(scope=_scope(), reader_context=_context())

    assert report.valid is True


def test_audit_accepts_a_valid_append_only_correction_history(graph: object) -> None:
    target = _node("fact:corrected")
    graph.write_batch(
        HeavenlyGraphWriteBatch(
            transaction_id="tx:audit:correction:seed",
            idempotency_key="idem:audit:correction:seed",
            scope=target.scope,
            nodes=[target],
        )
    )
    graph.correct(
        GraphCorrectionRequest(
            target_kind="node",
            target_id=target.node_id,
            target_revision=1,
            correction_kind="corrected",
            source_refs=["authority:audit:correction"],
            semantic_metadata=_metadata(),
            scope=target.scope,
        )
    )

    assert graph.audit_consistency(scope=_scope(), reader_context=_context()).errors == []


@pytest.mark.parametrize(
    ("fixture_kind", "error_id"),
    [
        ("orphan_relation", "HG-AUDIT-ORPHAN-RELATION"),
        ("revision_chain", "HG-AUDIT-REVISION-CHAIN"),
        ("provenance", "HG-AUDIT-PROVENANCE"),
        ("scope", "HG-AUDIT-SCOPE"),
        ("semantic", "HG-AUDIT-SEMANTIC-TYPE"),
        ("correction", "HG-AUDIT-CORRECTION-LINK"),
    ],
)
def test_audit_reports_each_historical_invariant_with_a_stable_error_id(
    graph: object,
    fixture_kind: str,
    error_id: str,
) -> None:
    _inject_invalid_fixture(graph, kind=fixture_kind)

    report = HeavenlyGraphConsistencyAudit(graph).audit(_scope(), _context())

    assert [error.error_id for error in report.errors] == [error_id]
    assert report.errors[0].category


def test_audit_is_read_only_and_orders_errors_deterministically(graph: object) -> None:
    _inject_invalid_fixture(graph, kind="semantic")
    _inject_invalid_fixture(graph, kind="orphan_relation")
    before_nodes = deepcopy(graph._nodes)
    before_relations = deepcopy(graph._relations)

    first = HeavenlyGraphConsistencyAudit(graph).audit(_scope(), _context())
    second = HeavenlyGraphConsistencyAudit(graph).audit(_scope(), _context())

    assert first == second
    assert [error.error_id for error in first.errors] == sorted(error.error_id for error in first.errors)
    assert graph._nodes == before_nodes
    assert graph._relations == before_relations


def test_audit_redacts_inaccessible_payload_but_retains_the_error_category(graph: object) -> None:
    _inject_invalid_fixture(graph, kind="semantic")
    private_context = _context(principal="reader:outside", scopes=("actor_private",))

    report = HeavenlyGraphConsistencyAudit(graph).audit(_scope(), private_context)

    assert report.errors[0].error_id == "HG-AUDIT-SEMANTIC-TYPE"
    assert report.errors[0].category == "unsupported_semantic_type"
    assert report.errors[0].redacted is True
    assert report.errors[0].entity_ref is None
    assert report.errors[0].payload == {"redacted": True}
