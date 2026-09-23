from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.behavior_turn import (
    BEHAVIOR_TURN_STAGE_ORDER,
    BEHAVIOR_TURN_STAGE_TRANSITIONS,
    BehaviorTurnOutcome,
    BehaviorTurnStage,
)


CharacterTurnLifecycle = Literal[
    "prepared",
    "running",
    "awaiting_settlement",
    "settled",
    "evaluated",
    "committed",
    "rejected",
    "recovery_required",
    "abandoned",
    "failed",
]


class TurnLifecycleError(ValueError):
    """Raised when a canonical turn would leave its closed lifecycle."""


# This is the single normal-path stage/lifecycle table.  The graph projection
# derives its stage order from the same source; checkpoints remain receipts.
CHARACTER_TURN_STAGE_TRANSITIONS = BEHAVIOR_TURN_STAGE_TRANSITIONS

_TRANSITION_BY_STAGE = {
    stage: (before, after)
    for stage, before, after in CHARACTER_TURN_STAGE_TRANSITIONS
}


def expected_next_stage(
    stage_refs: dict[str, str], lifecycle: CharacterTurnLifecycle
) -> BehaviorTurnStage:
    """Return the only stage that may be appended to this canonical turn."""
    recorded_stages = tuple(stage_refs)
    expected_prefix = BEHAVIOR_TURN_STAGE_ORDER[: len(recorded_stages)]
    if recorded_stages != expected_prefix:
        raise TurnLifecycleError("stage records must follow canonical order")
    if len(recorded_stages) == len(BEHAVIOR_TURN_STAGE_ORDER):
        expected_lifecycle = _TRANSITION_BY_STAGE[recorded_stages[-1]][1]
        if lifecycle != expected_lifecycle:
            raise TurnLifecycleError(
                f"lifecycle {lifecycle} cannot advance; expected {expected_lifecycle}"
            )
        raise TurnLifecycleError("turn has no remaining canonical stage")
    next_stage = BEHAVIOR_TURN_STAGE_ORDER[len(recorded_stages)]
    expected_lifecycle = (
        "prepared"
        if not recorded_stages
        else _TRANSITION_BY_STAGE[recorded_stages[-1]][1]
    )
    if lifecycle != expected_lifecycle:
        raise TurnLifecycleError(
            f"lifecycle {lifecycle} cannot advance; expected {expected_lifecycle}"
        )
    return next_stage


def lifecycle_after(stage: BehaviorTurnStage) -> CharacterTurnLifecycle:
    """Return the lifecycle reached after the given legal canonical stage."""
    return _TRANSITION_BY_STAGE[stage][1]


class CharacterTurnStageEvent(BaseModel):
    """Actor-private canonical stage event, before compact graph projection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    stage: BehaviorTurnStage
    stage_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    producer_ts: int = Field(ge=0)
    outcome: BehaviorTurnOutcome = "recorded"


class CharacterTurnReceipt(BaseModel):
    """A separately typed continuity checkpoint/receipt, never a turn stage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    lifecycle: CharacterTurnLifecycle
    producer_ts: int = Field(ge=0)
    snapshot_revision: int = Field(ge=0)
    receipt_ref: str | None = Field(default=None, min_length=1)
    checkpoint_ref: str | None = Field(default=None, min_length=1)


class CharacterTurnContext(BaseModel):
    """Immutable identity and legal lifecycle state for one actor behavior turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    source_event_ref: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    lifecycle: CharacterTurnLifecycle
    stage_refs: dict[str, str] = Field(default_factory=dict)
    stage_idempotency_keys: dict[str, str] = Field(default_factory=dict)
    input_revision_vector: dict[str, int]
    memory_revision_vector: dict[str, int]
    policy_revision: str = Field(min_length=1)
    snapshot_revision: int = Field(ge=0)
    branch_id: str | None = Field(default=None, min_length=1)
    producer_ts: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_stage_state(self) -> "CharacterTurnContext":
        if tuple(self.stage_refs) != tuple(self.stage_idempotency_keys):
            raise ValueError("stage refs and idempotency keys must have matching stages")
        for stage, ref in self.stage_refs.items():
            if stage not in _TRANSITION_BY_STAGE or not ref:
                raise ValueError("stage refs must use known stages with non-empty refs")
        if any(not key for key in self.stage_idempotency_keys.values()):
            raise ValueError("stage idempotency keys must be non-empty")
        if len(self.stage_refs) == len(BEHAVIOR_TURN_STAGE_ORDER):
            expected_lifecycle = _TRANSITION_BY_STAGE["policy"][1]
            if self.lifecycle != expected_lifecycle:
                raise ValueError(
                    f"completed turn lifecycle must be {expected_lifecycle}"
                )
        else:
            expected_next_stage(self.stage_refs, self.lifecycle)
        return self

    @classmethod
    def begin(
        cls,
        actor_id: str,
        source_event_ref: str,
        producer_ts: int,
        *,
        causation_id: str,
        correlation_id: str,
        input_revision_vector: dict[str, int],
        memory_revision_vector: dict[str, int],
        policy_revision: str,
        snapshot_revision: int,
        branch_id: str | None = None,
    ) -> "CharacterTurnContext":
        return cls(
            turn_id=f"turn:{actor_id}:{source_event_ref}",
            actor_id=actor_id,
            source_event_ref=source_event_ref,
            causation_id=causation_id,
            correlation_id=correlation_id,
            lifecycle="prepared",
            input_revision_vector=dict(input_revision_vector),
            memory_revision_vector=dict(memory_revision_vector),
            policy_revision=policy_revision,
            snapshot_revision=snapshot_revision,
            branch_id=branch_id,
            producer_ts=producer_ts,
        )

    def advance(
        self,
        stage: BehaviorTurnStage,
        *,
        stage_ref: str,
        idempotency_key: str,
        producer_ts: int,
    ) -> "CharacterTurnContext":
        if producer_ts < 0:
            raise TurnLifecycleError("producer_ts must be non-negative")
        if not stage_ref or not idempotency_key:
            raise TurnLifecycleError("stage ref and idempotency key are required")
        if stage in self.stage_refs:
            if (
                self.stage_refs[stage] != stage_ref
                or self.stage_idempotency_keys[stage] != idempotency_key
            ):
                raise TurnLifecycleError("stage idempotency payload mismatch")
            return self
        expected_stage = expected_next_stage(self.stage_refs, self.lifecycle)
        if stage != expected_stage:
            raise TurnLifecycleError(f"expected {expected_stage}, got {stage}")
        return self.model_copy(
            update={
                "stage_refs": {**self.stage_refs, stage: stage_ref},
                "stage_idempotency_keys": {
                    **self.stage_idempotency_keys,
                    stage: idempotency_key,
                },
                "lifecycle": lifecycle_after(stage),
            }
        )

    def stage_event(
        self,
        stage: BehaviorTurnStage,
        *,
        stage_ref: str,
        idempotency_key: str,
        producer_ts: int,
        outcome: BehaviorTurnOutcome = "recorded",
    ) -> tuple["CharacterTurnContext", CharacterTurnStageEvent]:
        """Advance and return the matching canonical session event."""
        advanced = self.advance(
            stage,
            stage_ref=stage_ref,
            idempotency_key=idempotency_key,
            producer_ts=producer_ts,
        )
        return advanced, CharacterTurnStageEvent(
            turn_id=advanced.turn_id,
            actor_id=advanced.actor_id,
            correlation_id=advanced.correlation_id,
            causation_id=advanced.causation_id,
            stage=stage,
            stage_ref=stage_ref,
            idempotency_key=idempotency_key,
            producer_ts=producer_ts,
            outcome=outcome,
        )

    def receipt(
        self,
        *,
        producer_ts: int,
        receipt_ref: str | None = None,
        checkpoint_ref: str | None = None,
    ) -> CharacterTurnReceipt:
        return CharacterTurnReceipt(
            turn_id=self.turn_id,
            actor_id=self.actor_id,
            correlation_id=self.correlation_id,
            lifecycle=self.lifecycle,
            producer_ts=producer_ts,
            snapshot_revision=self.snapshot_revision,
            receipt_ref=receipt_ref,
            checkpoint_ref=checkpoint_ref,
        )


__all__ = [
    "CHARACTER_TURN_STAGE_TRANSITIONS",
    "CharacterTurnContext",
    "CharacterTurnLifecycle",
    "CharacterTurnReceipt",
    "CharacterTurnStageEvent",
    "TurnLifecycleError",
    "expected_next_stage",
    "lifecycle_after",
]
