import pytest
from pathlib import Path
from pydantic import ValidationError

from app.models.siming_heavenly_graph import (
    GraphCorrectionRequest,
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
from app.services.siming_heavenly_graph_port import (
    HeavenlyGraphIdempotencyConflict,
    HeavenlyGraphRevisionConflict,
)


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


def test_adapter_rejects_legacy_node_namespace_and_visibility(graph_adapter: object) -> None:
    invalid_namespace = HeavenlyGraphNode(
        node_id="story:private",
        node_type="authored_story_blueprint",
        scope=_scope("actor_private", owner="char_b"),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=_provenance(),
    )
    with pytest.raises(ValueError, match="legacy node namespace"):
        graph_adapter.write_batch(_write_batch(invalid_namespace))

    invalid_visibility = invalid_namespace.model_copy(
        update={
            "scope": _scope(),
            "semantic_metadata": _metadata(visibility_scope="siming_internal", policy_revision="policy:legacy"),
        },
        deep=True,
    )
    with pytest.raises(ValueError, match="legacy node visibility"):
        graph_adapter.write_batch(_write_batch(invalid_visibility))


def test_adapter_rejects_legacy_relation_cross_namespace(graph_adapter: object) -> None:
    from app.models.siming_heavenly_graph import HeavenlyGraphWriteBatch

    relation = HeavenlyGraphRelation(
        relation_id="legacy:invalid-scope",
        relation_type="actor_memory:references_actor",
        source_node_id="private:source",
        target_node_id="fact:target",
        scope=_scope(),
        validity=GraphValidity(valid_from=1),
        recorded_at=1,
        revision=1,
        provenance=_provenance(),
        semantic_metadata=GraphSemanticMetadata(),
    )
    batch = HeavenlyGraphWriteBatch(
        transaction_id="graph_tx:legacy-invalid-scope",
        idempotency_key="semantic-admission:legacy-invalid-scope",
        scope=relation.scope,
        relations=[relation],
    )
    with pytest.raises(ValueError, match="legacy relation namespace"):
        graph_adapter.write_batch(batch)


def _correction_target() -> HeavenlyGraphNode:
    return HeavenlyGraphNode(
        node_id="fact:correctable",
        node_type="world_fact",
        scope=_scope(),
        validity=GraphValidity(valid_from=10),
        recorded_at=10,
        revision=1,
        provenance=_provenance(),
        semantic_metadata=_metadata(),
    )


def _correction_request(
    *,
    correction_kind: str = "corrected",
    expected_revision_vector: object | None = None,
    source_refs: list[str] | None = None,
) -> GraphCorrectionRequest:
    return GraphCorrectionRequest(
        target_kind="node",
        target_id="fact:correctable",
        target_revision=1,
        correction_kind=correction_kind,
        source_refs=(
            ["authority:event:correction"]
            if source_refs is None
            else source_refs
        ),
        semantic_metadata=_metadata(),
        expected_revision_vector=expected_revision_vector,
    )


def test_correction_appends_revision_and_preserves_auditable_history(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))

    result = graph_adapter.correct(_correction_request())

    assert result.applied is True
    assert result.node_refs
    current = graph_adapter.get_node(
        node_id=target.node_id,
        scope=target.scope,
        valid_at=10,
        recorded_at=11,
    )
    assert current is not None
    assert current.revision == 2
    assert current.supersedes_revision == 1
    assert current.semantic_metadata.derivation_kind == "correction"
    assert current.attributes["correction_target_id"] == target.node_id
    assert current.attributes["correction_target_source_ref"] == "authority:event:1"
    assert current.semantic_metadata.source_event_refs == (
        "authority:event:1",
        "authority:event:correction",
    )

    historical = graph_adapter.get_node(
        node_id=target.node_id,
        scope=target.scope,
        valid_at=10,
        recorded_at=10,
    )
    assert historical is not None
    assert historical.revision == 1


def test_retraction_is_excluded_from_default_current_query_but_history_remains(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    graph_adapter.correct(_correction_request(correction_kind="retracted"))

    assert graph_adapter.get_node(
        node_id=target.node_id,
        scope=target.scope,
        valid_at=10,
    ) is None
    historical = graph_adapter.get_node(
        node_id=target.node_id,
        scope=target.scope,
        valid_at=10,
        recorded_at=10,
    )
    assert historical is not None and historical.revision == 1


def test_redaction_is_excluded_from_default_current_query(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    graph_adapter.correct(_correction_request(correction_kind="redacted"))

    assert graph_adapter.get_node(
        node_id=target.node_id,
        scope=target.scope,
        valid_at=10,
    ) is None


def test_correction_keeps_concurrent_conflict_claims(graph_adapter: object) -> None:
    first = _correction_target().model_copy(update={"node_id": "claim:a"})
    second = _correction_target().model_copy(update={"node_id": "claim:b"})
    graph_adapter.write_batch(
        _write_batch(first).model_copy(update={"idempotency_key": "claim:a"})
    )
    graph_adapter.write_batch(
        _write_batch(second).model_copy(update={"idempotency_key": "claim:b"})
    )
    graph_adapter.correct(
        GraphCorrectionRequest(
            target_kind="node",
            target_id="claim:a",
            target_revision=1,
            correction_kind="corrected",
            source_refs=["authority:event:claim-a-correction"],
            semantic_metadata=_metadata(),
        )
    )
    assert graph_adapter.get_node(
        node_id="claim:b", scope=first.scope, valid_at=10
    ) is not None


def test_stale_expected_revision_vector_rejects_without_any_write(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    stale = _correction_request(
        expected_revision_vector=GraphRevisionVector(node_revision=0)
    )

    with pytest.raises(HeavenlyGraphRevisionConflict) as exc_info:
        graph_adapter.correct(stale)

    conflict = exc_info.value
    assert conflict.expected_revision_vector == GraphRevisionVector(node_revision=0)
    assert conflict.current_revision_vector.node_revision == 1
    assert target.node_id in conflict.affected_refs
    assert graph_adapter.has_idempotency_key(
        scope=target.scope,
        idempotency_key="graph:correction:node:fact:correctable:1:corrected",
    ) is False
    current = graph_adapter.get_node(
        node_id=target.node_id, scope=target.scope, valid_at=10
    )
    assert current is not None and current.revision == 1


def test_correction_rejects_missing_source_linkage_before_write(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    with pytest.raises(ValueError, match="source"):
        graph_adapter.correct(_correction_request(source_refs=[]))
    current = graph_adapter.get_node(
        node_id=target.node_id, scope=target.scope, valid_at=10
    )
    assert current is not None and current.revision == 1


def test_correction_requires_current_immediate_predecessor(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    graph_adapter.correct(_correction_request())

    with pytest.raises(HeavenlyGraphRevisionConflict, match="not current"):
        graph_adapter.correct(
            _correction_request(
                correction_kind="redacted",
                source_refs=["authority:event:second-correction"],
            )
        )

    current = graph_adapter.get_node(
        node_id=target.node_id, scope=target.scope, valid_at=10
    )
    assert current is not None and current.revision == 2


@pytest.mark.parametrize(
    ("metadata", "error"),
    [
        (_metadata(policy_revision="policy:v2"), "policy revision"),
        (_metadata(visibility_scope="authority_only"), "visibility scope"),
    ],
)
def test_correction_rejects_mismatched_semantic_scope_before_write(
    graph_adapter: object,
    metadata: GraphSemanticMetadata,
    error: str,
) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    request = _correction_request().model_copy(
        update={"semantic_metadata": metadata}, deep=True
    )

    with pytest.raises(ValueError, match=error):
        graph_adapter.correct(request)

    current = graph_adapter.get_node(
        node_id=target.node_id, scope=target.scope, valid_at=10
    )
    assert current is not None and current.revision == 1


def test_correction_is_idempotent_and_changed_payload_is_rejected(graph_adapter: object) -> None:
    target = _correction_target()
    graph_adapter.write_batch(_write_batch(target))
    request = _correction_request()
    first = graph_adapter.correct(request)
    replay = graph_adapter.correct(request)
    assert first.applied is True
    assert replay.applied is False and replay.replayed is True
    with pytest.raises(HeavenlyGraphIdempotencyConflict, match="idempotency key"):
        graph_adapter.correct(
            request.model_copy(
                update={"source_refs": ["authority:event:changed"]}, deep=True
            )
        )


def test_sqlite_correction_history_and_idempotency_survive_restart(tmp_path: Path) -> None:
    database = tmp_path / "correction-restart.db"
    target = _correction_target()
    request = _correction_request()
    first = SQLiteHeavenlyGraphAdapter(database)
    first.write_batch(_write_batch(target))
    applied = first.correct(request)
    first.close()

    reopened = SQLiteHeavenlyGraphAdapter(database)
    replay = reopened.correct(request)
    current = reopened.get_node(
        node_id=target.node_id, scope=target.scope, valid_at=10
    )
    historical = reopened.get_node(
        node_id=target.node_id, scope=target.scope, valid_at=10, recorded_at=10
    )
    reopened.close()
    assert applied.applied is True
    assert replay.replayed is True and replay.applied is False
    assert current is not None and current.revision == 2
    assert historical is not None and historical.revision == 1
