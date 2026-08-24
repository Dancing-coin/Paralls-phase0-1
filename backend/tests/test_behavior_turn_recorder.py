import pytest

from app.models.behavior_turn import (
    BehaviorTurnRecordRequest,
    BehaviorTurnStageRecord,
)
from app.models.siming_heavenly_graph import (
    BehaviorTurnQuery,
    GraphProvenance,
    GraphReaderContext,
    GraphRevisionVector,
    HeavenlyGraphScope,
    HeavenlyNodeQuery,
)
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter


STAGES = (
    "context",
    "interpretation",
    "goal",
    "intent",
    "execution",
    "settlement",
    "evaluation",
    "policy",
)


def _scope() -> HeavenlyGraphScope:
    return HeavenlyGraphScope(
        world_id="world:test",
        session_id="session:test",
        story_branch_id="branch:main",
        graph_namespace="actor_private",
        owner_actor_id="char_b",
    )


def _request(
    *, stages: tuple[BehaviorTurnStageRecord, ...] | None = None
) -> BehaviorTurnRecordRequest:
    return BehaviorTurnRecordRequest(
        turn_id="turn:char-b:1",
        scope=_scope(),
        valid_at=10,
        recorded_at=11,
        policy_revision="policy:v3",
        source_revision_vector=GraphRevisionVector(
            node_revision=4,
            relation_revision=3,
            source_revision=8,
            policy_revision=3,
            branch_revision=2,
        ),
        scope_digest="scope:char-b:main",
        provenance=GraphProvenance(
            source_kind="runtime_outcome",
            source_ref="character-turn:1",
            causation_id="cause:character-turn:1",
            correlation_id="corr:character-turn:1",
            producer_system="character_agent_runtime",
            actor_id="char_b",
        ),
        transaction_id="tx:character-turn:1",
        idempotency_key="character-turn:1",
        stages=stages
        or tuple(
            BehaviorTurnStageRecord(
                stage=stage,
                outcome="committed" if stage == "settlement" else "recorded",
                source_refs=(f"source:{stage}",),
                payload={"summary": f"recorded {stage}"},
            )
            for stage in STAGES
        ),
    )


def _context() -> GraphReaderContext:
    return GraphReaderContext(
        reader_principal="reader:char_b",
        allowed_visibility_scopes=("actor_private",),
        world_id="world:test",
        session_id="session:test",
        story_branch_id="branch:main",
        valid_at=10,
        recorded_at=11,
        policy_revision="policy:v3",
    )


def test_records_complete_actor_turn_as_queryable_stage_chain() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    recorder = BehaviorTurnRecorder(graph)

    first = recorder.record(_request())
    replay = recorder.record(_request())

    assert first.applied is True
    assert replay.replayed is True
    result = graph.query_semantic(
        BehaviorTurnQuery(
            context=_context(),
            scope=_scope(),
            turn_id="turn:char-b:1",
            correlation_id="corr:character-turn:1",
            actor_id="char_b",
        )
    )
    stage_nodes = [
        node for node in result.nodes if node.attributes.get("entity_kind") == "stage"
    ]
    assert [node.attributes["stage"] for node in stage_nodes] == list(STAGES)
    assert all(node.semantic_metadata.record_kind == "projection" for node in result.nodes)
    assert all(
        node.semantic_metadata.source_revision_vector.source_revision == 8
        for node in result.nodes
    )
    assert all(node.semantic_metadata.scope_digest == "scope:char-b:main" for node in result.nodes)
    assert [relation.attributes["stage"] for relation in result.relations] == list(STAGES)
    assert all(relation.relation_type == "part_of_turn" for relation in result.relations)


def test_retains_rejected_settlement_without_creating_authority_fact() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    recorder = BehaviorTurnRecorder(graph)
    stages = tuple(
        BehaviorTurnStageRecord(
            stage=stage,
            outcome=(
                "rejected"
                if stage == "settlement"
                else "failed"
                if stage == "evaluation"
                else "recorded"
            ),
            source_refs=("authority:rejection",) if stage == "settlement" else (),
            payload={"error_code": "constraint_denied"}
            if stage in {"settlement", "evaluation"}
            else {},
        )
        for stage in STAGES
    )

    recorder.record(_request(stages=stages))

    result = graph.query_semantic(
        BehaviorTurnQuery(
            context=_context(),
            scope=_scope(),
            turn_id="turn:char-b:1",
            stage="settlement",
        )
    )
    stage_nodes = [
        node for node in result.nodes if node.attributes.get("entity_kind") == "stage"
    ]
    assert len(stage_nodes) == 1
    assert stage_nodes[0].attributes["outcome"] == "rejected"
    assert stage_nodes[0].attributes["payload"] == {
        "error_code": "constraint_denied"
    }
    assert stage_nodes[0].semantic_metadata.record_kind == "projection"
    assert stage_nodes[0].semantic_metadata.derivation_kind == "projection"


def test_rejects_non_contiguous_stage_order_before_graph_write() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    recorder = BehaviorTurnRecorder(graph)
    stages = (
        BehaviorTurnStageRecord(stage="context", payload={}),
        BehaviorTurnStageRecord(stage="goal", payload={}),
    )

    with pytest.raises(ValueError, match="contiguous canonical order"):
        recorder.record(_request(stages=stages))

    assert graph.query_nodes(HeavenlyNodeQuery(scope=_scope(), valid_at=10)) == []
