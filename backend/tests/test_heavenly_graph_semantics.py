import pytest
from pathlib import Path
from pydantic import ValidationError

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphReaderContext,
    GraphRevisionVector,
    GraphSemanticMetadata,
    GraphValidity,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
)
from app.services.heavenly_graph_semantics import (
    HeavenlyNodeTypeRegistry,
    HeavenlyRelationTypeRegistry,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter


def _scope(namespace: str = "siming_heavenly", owner: str | None = None) -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        graph_namespace=namespace,
        owner_actor_id=owner,
    )


def _provenance() -> GraphProvenance:
    return GraphProvenance(
        source_kind="authority_event",
        source_ref="authority:event:1",
        causation_id="cause:1",
        correlation_id="corr:1",
        producer_system="system_l6",
    )


def _metadata(**overrides: object) -> GraphSemanticMetadata:
    values: dict[str, object] = {
        "record_kind": "fact",
        "visibility_scope": "public",
        "derivation_kind": "authority",
        "source_event_refs": ["authority:event:1"],
        "source_revision_vector": GraphRevisionVector(source_revision=1),
        "policy_revision": "policy:v1",
        "scope_digest": "scope:demo",
    }
    values.update(overrides)
    return GraphSemanticMetadata(**values)


def test_semantic_metadata_rejects_unknown_record_kind() -> None:
    with pytest.raises(ValidationError):
        _metadata(record_kind="belief")


def test_semantic_metadata_rejects_unknown_visibility_scope() -> None:
    with pytest.raises(ValidationError):
        _metadata(visibility_scope="friends_only")


def test_graph_reader_context_requires_all_scope_and_time_fields() -> None:
    with pytest.raises(ValidationError):
        GraphReaderContext(reader_principal="reader:char_b")

    context = GraphReaderContext(
        reader_principal="reader:char_b",
        allowed_visibility_scopes=["public", "actor_private"],
        world_id="world:demo",
        session_id="session:demo",
        story_branch_id="branch:main",
        valid_at=10,
        recorded_at=12,
        policy_revision="policy:v1",
    )
    assert context.allowed_visibility_scopes == ("public", "actor_private")


def test_actor_private_scope_requires_owner_actor() -> None:
    with pytest.raises(ValidationError, match="owner_actor_id"):
        _scope("actor_private")


def test_graph_records_carry_typed_semantic_metadata() -> None:
    node = HeavenlyGraphNode(
        node_id="fact:lamp",
        node_type="world_fact",
        scope=_scope(),
        validity=GraphValidity(valid_from=10),
        recorded_at=12,
        revision=1,
        provenance=_provenance(),
        semantic_metadata=_metadata(),
    )
    assert node.semantic_metadata.record_kind == "fact"
    assert isinstance(node.semantic_metadata.source_revision_vector, GraphRevisionVector)


def test_node_registry_rejects_unknown_type_and_bad_namespace() -> None:
    registry = HeavenlyNodeTypeRegistry()
    with pytest.raises(ValueError, match="unregistered"):
        registry.validate(
            node_type="unknown_node",
            namespace="siming_heavenly",
            record_kind="fact",
            visibility_scope="public",
        )
    with pytest.raises(ValueError, match="namespace"):
        registry.validate(
            node_type="world_fact",
            namespace="actor_private",
            record_kind="fact",
            visibility_scope="public",
        )


def test_node_registry_enforces_actor_private_ownership_and_proposals() -> None:
    registry = HeavenlyNodeTypeRegistry()
    with pytest.raises(ValueError, match="owner_actor_id"):
        registry.validate(
            node_type="actor_view",
            namespace="actor_private",
            record_kind="projection",
            visibility_scope="actor_private",
        )
    registry.validate(
        node_type="policy_candidate",
        namespace="siming_heavenly",
        record_kind="proposal",
        visibility_scope="siming_internal",
    )
    with pytest.raises(ValueError, match="record_kind"):
        registry.validate(
            node_type="policy_candidate",
            namespace="siming_heavenly",
            record_kind="fact",
            visibility_scope="siming_internal",
        )


def test_relation_registry_rejects_forbidden_cross_namespace_relation() -> None:
    registry = HeavenlyRelationTypeRegistry()
    registry.validate(
        relation_type="observed_as",
        source_namespace="actor_private",
        target_namespace="siming_heavenly",
        record_kind="projection",
        visibility_scope="actor_private",
        source_owner_actor_id="char_b",
    )
    with pytest.raises(ValueError, match="namespace"):
        registry.validate(
            relation_type="part_of_turn",
            source_namespace="actor_private",
            target_namespace="resource_capability",
            record_kind="projection",
            visibility_scope="actor_private",
        )


def test_relation_registry_classifies_fact_and_proposal() -> None:
    registry = HeavenlyRelationTypeRegistry()
    registry.validate(
        relation_type="caused_by",
        source_namespace="siming_heavenly",
        target_namespace="siming_heavenly",
        record_kind="fact",
        visibility_scope="public",
    )
    registry.validate(
        relation_type="targets_attractor",
        source_namespace="siming_heavenly",
        target_namespace="siming_heavenly",
        record_kind="proposal",
        visibility_scope="siming_internal",
    )


def _write_batch(node: HeavenlyGraphNode) -> object:
    from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch

    return HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:semantic-admission",
        idempotency_key="semantic-admission:1",
        scope=node.scope,
        nodes=[node],
    )


@pytest.fixture(params=["memory", "sqlite"])
def graph_adapter(request: pytest.FixtureRequest, tmp_path: Path) -> object:
    if request.param == "sqlite":
        adapter = SQLiteHeavenlyGraphAdapter(tmp_path / "graph.db")
        yield adapter
        adapter.close()
        return
    yield InMemoryHeavenlyGraphAdapter()


def test_adapter_rejects_unknown_node_type_before_idempotency(graph_adapter: object) -> None:
    node = HeavenlyGraphNode(
        node_id="unknown:1",
        node_type="unknown_node",
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=_provenance(),
        semantic_metadata=_metadata(),
    )
    with pytest.raises(ValueError, match="unregistered"):
        graph_adapter.write_batch(_write_batch(node))
    assert not graph_adapter.has_idempotency_key(scope=node.scope, idempotency_key="semantic-admission:1")


def test_adapter_rejects_unknown_legacy_node_name(graph_adapter: object) -> None:
    node = HeavenlyGraphNode(
        node_id="unknown:legacy",
        node_type="unknown_legacy_node",
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=_provenance(),
    )
    with pytest.raises(ValueError, match="unregistered"):
        graph_adapter.write_batch(_write_batch(node))


def test_adapter_rejects_unknown_relation_type_before_idempotency(graph_adapter: object) -> None:
    from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch

    relation = HeavenlyGraphRelation(
        relation_id="unknown:relation",
        relation_type="unknown_relation",
        source_node_id="fact:source",
        target_node_id="fact:target",
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=_provenance(),
        semantic_metadata=_metadata(),
    )
    batch = HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:unknown-relation",
        idempotency_key="semantic-admission:relation",
        scope=relation.scope,
        relations=[relation],
    )
    with pytest.raises(ValueError, match="unregistered"):
        graph_adapter.write_batch(batch)
    assert not graph_adapter.has_idempotency_key(
        scope=relation.scope,
        idempotency_key="semantic-admission:relation",
    )


def test_adapter_rejects_invalid_semantic_namespace_and_visibility(graph_adapter: object) -> None:
    owner_scope = _scope("actor_private", owner="char_b")
    invalid_namespace = HeavenlyGraphNode(
        node_id="fact:private",
        node_type="world_fact",
        scope=owner_scope,
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=_provenance(),
        semantic_metadata=_metadata(),
    )
    with pytest.raises(ValueError, match="namespace"):
        graph_adapter.write_batch(_write_batch(invalid_namespace))

    invalid_visibility = invalid_namespace.model_copy(
        update={
            "scope": _scope(),
            "semantic_metadata": _metadata(visibility_scope="siming_internal"),
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="visibility"):
        graph_adapter.write_batch(_write_batch(invalid_visibility))
