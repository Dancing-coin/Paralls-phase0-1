import pytest
from pathlib import Path

from app import config as config_module
from app import main
from app.models.behavior_turn import (
    BEHAVIOR_TURN_STAGE_ORDER,
    BehaviorTurnRecordRequest,
    BehaviorTurnStageRecord,
)
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent
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


STAGES = BEHAVIOR_TURN_STAGE_ORDER


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


def test_character_runtime_records_rejected_action_as_complete_behavior_turn() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    recorder = BehaviorTurnRecorder(graph)
    runtime = CharacterAgentRuntime(
        behavior_turn_recorder=recorder,
        behavior_turn_scope_resolver=lambda actor_id: _scope().model_copy(
            update={"owner_actor_id": actor_id}
        ),
    )
    event = CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=1201,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="obj_letter is visible but out of reach",
        source_candidate_event_id="visual_fact:1201:char_b",
        clarity_score=1.0,
        certainty_score=1.0,
    )
    runtime.ingest_character_perceived_event(event)

    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=1202,
        payload={
            "result_id": "constraint:1202:char_b",
            "result_type": "constraint_state_result",
            "settlement_status": "rejected",
            "constraint_summary": "too far from obj_letter",
            "causation_id": "interact:1202",
            "correlation_id": "interact:1202",
            "policy_revision": "policy:character-runtime:v1",
            "authority_event_ref": "authority:event:accepted",
            "authority_owner_ref": "esm:world",
        },
    )

    context = _context().model_copy(
        update={
            "valid_at": 1202,
            "recorded_at": 1202,
            "policy_revision": "policy:character-runtime:v1",
        }
    )
    result = graph.query_semantic(
        BehaviorTurnQuery(
            context=context,
            scope=_scope(),
            correlation_id="interact:1202",
            actor_id="char_b",
        )
    )
    stage_nodes = [
        node for node in result.nodes if node.attributes.get("entity_kind") == "stage"
    ]
    assert [node.attributes["stage"] for node in stage_nodes] == list(STAGES)
    by_stage = {str(node.attributes["stage"]): node for node in stage_nodes}
    assert by_stage["settlement"].attributes["outcome"] == "rejected"
    assert by_stage["settlement"].attributes["payload"]["result_id"] == (
        "constraint:1202:char_b"
    )
    assert by_stage["evaluation"].attributes["outcome"] == "failed"
    assert by_stage["policy"].attributes["payload"]["status"] == "candidate_only"
    assert by_stage["policy"].semantic_metadata.source_event_refs
    assert "character_policy_candidate_event" in by_stage[
        "policy"
    ].semantic_metadata.source_event_refs[0]
    assert all(node.semantic_metadata.record_kind == "projection" for node in stage_nodes)


def test_application_runtime_wires_character_turns_to_shared_sqlite_graph(
    tmp_path: Path,
) -> None:
    state = main.build_runtime_state(
        config_module.Settings(
            heavenly_graph_path=str(tmp_path / "behavior-turn.sqlite3"),
            siming_heavenly_mode="off",
        )
    )
    event = CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=1401,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="obj_letter is visible",
        source_candidate_event_id="visual_fact:1401:char_b",
    )
    try:
        state.character_agent_runtime.ingest_character_perceived_event(event)
        state.character_agent_runtime.record_settlement_result(
            actor_id="char_b",
            producer_ts=1402,
            payload={
                "result_id": "object-state:1402",
                "result_type": "object_state_result",
                "settlement_status": "accepted",
                "change_summary": "obj_letter inspected",
                "causation_id": "interact:1402",
                "correlation_id": "interact:1402",
                "policy_revision": "policy:character-runtime:v1",
                "authority_event_ref": "authority:event:accepted",
                "authority_owner_ref": "esm:world",
            },
        )
        result = state.heavenly_graph.query_semantic(
            BehaviorTurnQuery(
                context=GraphReaderContext(
                    reader_principal="reader:char_b",
                    allowed_visibility_scopes=("actor_private",),
                    world_id="world:demo",
                    session_id="session:demo",
                    story_branch_id="branch:main",
                    valid_at=1402,
                    recorded_at=1402,
                    policy_revision="policy:character-runtime:v1",
                ),
                scope=main.actor_private_scope("char_b"),
                correlation_id="interact:1402",
                actor_id="char_b",
            )
        )
    finally:
        state.close()

    stage_nodes = [
        node for node in result.nodes if node.attributes.get("entity_kind") == "stage"
    ]
    assert [node.attributes["stage"] for node in stage_nodes] == list(STAGES)
    assert next(
        node for node in stage_nodes if node.attributes["stage"] == "settlement"
    ).attributes["outcome"] == "committed"


def test_character_projection_does_not_mix_interleaved_turn_events() -> None:
    graph = InMemoryHeavenlyGraphAdapter()
    recorder = BehaviorTurnRecorder(graph)
    runtime = CharacterAgentRuntime(
        behavior_turn_recorder=recorder,
        behavior_turn_scope_resolver=lambda actor_id: _scope().model_copy(
            update={"owner_actor_id": actor_id}
        ),
    )
    runtime.ingest_character_perceived_event(_event_for_test(200, "first"))
    runtime.ingest_character_perceived_event(_event_for_test(210, "second"))
    runtime.record_settlement_result(
        actor_id="char_b",
        producer_ts=211,
        payload={
            "result_id": "constraint:interleaved",
            "result_type": "constraint_state_result",
            "settlement_status": "rejected",
            "constraint_summary": "blocked",
            "causation_id": "cause:second",
            "correlation_id": "cause:second",
        },
    )
    result = graph.query_semantic(
        BehaviorTurnQuery(
            context=_context().model_copy(update={"valid_at": 211, "recorded_at": 211}),
            scope=_scope(),
            correlation_id="cause:second",
            actor_id="char_b",
        )
    )
    assert _stage_nodes_for_test(result) == []


def _event_for_test(timestamp: int, summary: str) -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id="char_b",
        percept_channel="visual",
        producer_ts=timestamp,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary=summary,
        source_candidate_event_id=f"visual:{timestamp}",
    )


def _stage_nodes_for_test(result: object) -> list[object]:
    return [
        node
        for node in result.nodes
        if node.attributes.get("entity_kind") == "stage"
    ]
