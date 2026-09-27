import pytest

from app.character_agent.models.turn_context import (
    CharacterTurnContext,
    CharacterTurnStageEvent,
    TurnLifecycleError,
)
from app.models.behavior_turn import BehaviorTurnRecordRequest, BehaviorTurnStageRecord
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    HeavenlyGraphScope,
    HeavenlyNodeQuery,
)
from app.services.behavior_turn_recorder import BehaviorTurnRecorder
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter


def test_turn_carries_one_identity_from_context_to_awaiting_settlement() -> None:
    """A missing or regenerated ID would sever the stage chain."""
    turn = CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="event:perception:1",
        producer_ts=100,
        causation_id="cause:1",
        correlation_id="corr:1",
        input_revision_vector={"l1": 4},
        memory_revision_vector={"memory": 9},
        policy_revision="policy:char_b:3",
        snapshot_revision=12,
    )

    for stage in ("context", "interpretation", "goal", "intent", "execution"):
        turn = turn.advance(
            stage,
            stage_ref=f"event:{stage}:1",
            idempotency_key=f"key:{stage}",
            producer_ts=101,
        )

    assert turn.turn_id == "turn:char_b:event:perception:1"
    assert turn.lifecycle == "awaiting_settlement"


def test_turn_rejects_out_of_order_or_changed_idempotent_stage() -> None:
    """Skipping context would create an invalid canonical projection."""
    turn = CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="event:perception:2",
        producer_ts=1,
        causation_id="cause:2",
        correlation_id="corr:2",
        input_revision_vector={"l1": 1},
        memory_revision_vector={"memory": 1},
        policy_revision="policy:char_b:1",
        snapshot_revision=1,
    )

    with pytest.raises(TurnLifecycleError, match="expected context"):
        turn.advance(
            "execution",
            stage_ref="event:execution:1",
            idempotency_key="k",
            producer_ts=1,
        )


def test_canonical_projection_rejects_stage_identity_outside_request_scope() -> None:
    """A foreign canonical event must never inherit this request's graph scope."""
    turn, canonical_stage = _turn_with_context_stage()
    foreign_stage = canonical_stage.model_copy(
        update={"turn_id": "turn:char_other:event:1", "actor_id": "char_other"}
    )

    with pytest.raises(ValueError, match="canonical stage identity"):
        _canonical_request(turn, foreign_stage)


def test_canonical_event_validates_branch_valid_time_and_revision_pins() -> None:
    """A projection with a foreign branch or revision must fail before graph write."""
    turn, stage_event = _turn_with_context_stage()

    with pytest.raises(ValueError, match="branch"):
        _canonical_request(
            turn,
            stage_event.model_copy(update={"branch_id": "branch:other"}),
        )
    with pytest.raises(ValueError, match="revision"):
        _canonical_request(
            turn,
            stage_event.model_copy(update={"snapshot_revision": 99}),
        )
    with pytest.raises(ValueError, match="valid"):
        _canonical_request(
            turn,
            stage_event.model_copy(update={"valid_at": 99}),
        )


def test_stage_replay_freezes_outcome_and_payload() -> None:
    """A duplicate stage key must not produce a conflicting canonical event."""
    turn = _turn(branch_id="branch:main")
    turn, first = turn.stage_event(
        "context",
        stage_ref="event:context:1",
        idempotency_key="key:context",
        producer_ts=2,
        payload={"l1": "seen"},
    )
    replayed, replay = turn.stage_event(
        "context",
        stage_ref="event:context:1",
        idempotency_key="key:context",
        producer_ts=2,
        payload={"l1": "seen"},
    )

    assert replayed is turn
    assert replay == first
    with pytest.raises(TurnLifecycleError, match="idempotency payload mismatch"):
        turn.stage_event(
            "context",
            stage_ref="event:context:1",
            idempotency_key="key:context",
            producer_ts=2,
            outcome="failed",
            payload={"l1": "seen"},
        )


def test_canonical_projection_reconstructs_nested_payload_before_persistence() -> None:
    """Mutating compact data after validation cannot alter canonical graph output."""
    turn = _turn(branch_id="branch:main")
    turn, event = turn.stage_event(
        "context",
        stage_ref="event:context:1",
        idempotency_key="key:context",
        producer_ts=2,
        payload={"nested": {"x": 1}},
    )
    request = _canonical_request(turn, event)
    request.stages[0].payload["nested"]["x"] = 9

    graph = InMemoryHeavenlyGraphAdapter()
    BehaviorTurnRecorder(graph).record(request)
    stage_node = next(
        node
        for node in graph.query_nodes(
            HeavenlyNodeQuery(scope=request.scope, valid_at=request.valid_at)
        )
        if node.attributes.get("entity_kind") == "stage"
    )

    assert stage_node.attributes["payload"] == {"nested": {"x": 1}}


def test_context_mappings_are_immutable_and_revision_entries_are_non_negative() -> None:
    """In-place mutation must not bypass lifecycle validation."""
    turn = _turn(branch_id="branch:main")

    with pytest.raises(TypeError):
        turn.stage_refs["context"] = "forged"
    with pytest.raises(TypeError):
        turn.input_revision_vector["l1"] = 99
    with pytest.raises(ValueError, match="non-negative"):
        CharacterTurnContext.begin(
            actor_id="char_b",
            source_event_ref="event:perception:negative",
            producer_ts=1,
            causation_id="cause:negative",
            correlation_id="corr:negative",
            input_revision_vector={"l1": -1},
            memory_revision_vector={"memory": 1},
            policy_revision="policy:char_b:1",
            snapshot_revision=1,
        )


def test_terminal_and_recovery_transitions_are_closed_and_receipt_is_pinned() -> None:
    """Recovery is legal only from an unresolved execution and carries full pins."""
    turn = _turn(branch_id="branch:main")
    for stage in ("context", "interpretation", "goal", "intent", "execution"):
        turn = turn.advance(
            stage,
            stage_ref=f"event:{stage}:1",
            idempotency_key=f"key:{stage}",
            producer_ts=2,
        )
    recovery = turn.transition(
        "recovery_required",
        transition_ref="recovery:1",
        idempotency_key="recovery:key:1",
        producer_ts=3,
        payload={"reason": "receipt_missing"},
    )
    assert recovery.transition(
        "recovery_required",
        transition_ref="recovery:1",
        idempotency_key="recovery:key:1",
        producer_ts=3,
        payload={"reason": "receipt_missing"},
    ) is recovery
    with pytest.raises(TurnLifecycleError, match="idempotency payload mismatch"):
        recovery.transition(
            "recovery_required",
            transition_ref="recovery:1",
            idempotency_key="recovery:key:changed",
            producer_ts=3,
            payload={"reason": "receipt_missing"},
        )
    with pytest.raises(TurnLifecycleError, match="idempotency payload mismatch"):
        recovery.transition(
            "recovery_required",
            transition_ref="recovery:changed",
            idempotency_key="recovery:key:1",
            producer_ts=3,
            payload={"reason": "receipt_missing"},
        )
    with pytest.raises(TurnLifecycleError, match="idempotency payload mismatch"):
        recovery.transition(
            "recovery_required",
            transition_ref="recovery:1",
            idempotency_key="recovery:key:1",
            producer_ts=3,
            payload={"reason": "changed"},
        )
    abandoned = recovery.transition(
        "abandoned",
        transition_ref="abandon:1",
        idempotency_key="abandon:key:1",
        producer_ts=4,
        payload={"reason": "operator_abandoned"},
    )
    receipt = abandoned.receipt(
        producer_ts=5,
        idempotency_key="receipt:key:1",
        checkpoint_ref="checkpoint:1",
    )

    assert receipt.branch_id == "branch:main"
    assert receipt.valid_at == 1
    assert receipt.causation_id == "cause:1"
    assert receipt.input_revision_vector == {"l1": 1}
    with pytest.raises(TurnLifecycleError, match="cannot transition"):
        turn.transition(
            "abandoned",
            transition_ref="abandon:invalid",
            idempotency_key="abandon:key:invalid",
            producer_ts=3,
            payload={},
        )


def test_compact_stages_require_explicit_legacy_reader_origin() -> None:
    """New live compact projections cannot bypass canonical event validation."""
    fields = _legacy_request_fields()

    with pytest.raises(ValueError, match="record origin"):
        BehaviorTurnRecordRequest(**fields)
    with pytest.raises(ValueError, match="explicit legacy reader"):
        BehaviorTurnRecordRequest(
            **fields,
            record_origin="legacy_reader",
            legacy_reader_ref="forged:legacy-reader",
        )

    request = BehaviorTurnRecordRequest.from_legacy_projection(
        **fields, legacy_reader_ref="legacy:behavior-turn:1"
    )
    assert request.record_origin == "legacy_reader"


def _turn(*, branch_id: str | None) -> CharacterTurnContext:
    return CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="event:perception:1",
        producer_ts=1,
        causation_id="cause:1",
        correlation_id="corr:1",
        input_revision_vector={"l1": 1},
        memory_revision_vector={"memory": 2},
        policy_revision="policy:char_b:1",
        snapshot_revision=3,
        branch_id=branch_id,
    )


def _turn_with_context_stage() -> tuple[CharacterTurnContext, CharacterTurnStageEvent]:
    return _turn(branch_id="branch:main").stage_event(
        "context",
        stage_ref="event:context:1",
        idempotency_key="key:context",
        producer_ts=2,
        payload={"l1": "seen"},
    )


def _canonical_request(
    turn: CharacterTurnContext, stage_event: CharacterTurnStageEvent
) -> BehaviorTurnRecordRequest:
    return BehaviorTurnRecordRequest.from_canonical_stage_events(
        **_legacy_request_fields(turn=turn), stage_events=(stage_event,)
    )


def _legacy_request_fields(
    *, turn: CharacterTurnContext | None = None
) -> dict[str, object]:
    return {
        "turn_id": turn.turn_id if turn else "turn:char_b:event:1",
        "scope": HeavenlyGraphScope(
            world_id="world:test",
            session_id="session:test",
            story_branch_id="branch:main",
            graph_namespace="actor_private",
            owner_actor_id="char_b",
        ),
        "valid_at": turn.valid_at if turn else 1,
        "recorded_at": 2,
        "policy_revision": turn.policy_revision if turn else "policy:char_b:1",
        "source_revision_vector": GraphRevisionVector(),
        "scope_digest": "scope:char_b",
        "provenance": GraphProvenance(
            source_kind="runtime_outcome",
            source_ref="event:context:1",
            causation_id=turn.causation_id if turn else "cause:1",
            correlation_id=turn.correlation_id if turn else "corr:1",
            producer_system="character_agent_runtime",
            actor_id="char_b",
        ),
        "transaction_id": "tx:1",
        "idempotency_key": "turn:1",
        "stages": (BehaviorTurnStageRecord(stage="context", payload={}),),
        "branch_id": turn.branch_id if turn else None,
        "input_revision_vector": turn.input_revision_vector if turn else None,
        "memory_revision_vector": turn.memory_revision_vector if turn else None,
        "snapshot_revision": turn.snapshot_revision if turn else None,
    }
