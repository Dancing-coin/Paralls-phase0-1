import pytest

from app.character_agent.models.turn_context import (
    CharacterTurnContext,
    CharacterTurnStageEvent,
    TurnLifecycleError,
)
from app.models.behavior_turn import BehaviorTurnRecordRequest
from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    HeavenlyGraphScope,
)


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
    canonical_stage = CharacterTurnStageEvent(
        turn_id="turn:char_other:event:1",
        actor_id="char_other",
        correlation_id="corr:other",
        causation_id="cause:other",
        stage="context",
        stage_ref="event:context:1",
        idempotency_key="stage:context:1",
        producer_ts=1,
    )

    with pytest.raises(ValueError, match="canonical stage identity"):
        BehaviorTurnRecordRequest.from_canonical_stage_events(
            turn_id="turn:char_b:event:1",
            scope=HeavenlyGraphScope(
                world_id="world:test",
                session_id="session:test",
                story_branch_id="branch:main",
                graph_namespace="actor_private",
                owner_actor_id="char_b",
            ),
            valid_at=1,
            recorded_at=1,
            policy_revision="policy:char_b:1",
            source_revision_vector=GraphRevisionVector(),
            scope_digest="scope:char_b",
            provenance=GraphProvenance(
                source_kind="runtime_outcome",
                source_ref="event:context:1",
                causation_id="cause:1",
                correlation_id="corr:1",
                producer_system="character_agent_runtime",
                actor_id="char_b",
            ),
            transaction_id="tx:1",
            idempotency_key="turn:1",
            stage_events=(canonical_stage,),
        )
