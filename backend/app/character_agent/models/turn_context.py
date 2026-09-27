from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from app.models.behavior_turn import (
    BEHAVIOR_TURN_STAGE_ORDER,
    BEHAVIOR_TURN_STAGE_TRANSITIONS,
    BehaviorTurnOutcome,
    BehaviorTurnStage,
    CharacterTurnStageEvent,
)


CharacterTurnLifecycle = Literal[
    "prepared", "running", "awaiting_settlement", "settled", "evaluated",
    "committed", "rejected", "recovery_required", "abandoned", "failed",
]


class TurnLifecycleError(ValueError):
    """Raised when a canonical turn would leave its closed lifecycle."""


CHARACTER_TURN_STAGE_TRANSITIONS = BEHAVIOR_TURN_STAGE_TRANSITIONS
_TRANSITION_BY_STAGE = {
    stage: (before, after)
    for stage, before, after in CHARACTER_TURN_STAGE_TRANSITIONS
}
_TERMINAL_LIFECYCLE_TRANSITIONS: frozenset[
    tuple[CharacterTurnLifecycle, CharacterTurnLifecycle]
] = frozenset({
    ("awaiting_settlement", "recovery_required"),
    ("settled", "rejected"),
    ("recovery_required", "abandoned"),
    ("prepared", "failed"),
    ("running", "failed"),
    ("awaiting_settlement", "failed"),
    ("settled", "failed"),
    ("evaluated", "failed"),
})


def _normal_lifecycle(stage_refs: Mapping[str, str]) -> CharacterTurnLifecycle:
    recorded_stages = tuple(stage_refs)
    if recorded_stages != BEHAVIOR_TURN_STAGE_ORDER[: len(recorded_stages)]:
        raise TurnLifecycleError("stage records must follow canonical order")
    return "prepared" if not recorded_stages else _TRANSITION_BY_STAGE[recorded_stages[-1]][1]


def expected_next_stage(
    stage_refs: Mapping[str, str], lifecycle: CharacterTurnLifecycle
) -> BehaviorTurnStage:
    """Return the only stage that may be appended to this canonical turn."""
    normal_lifecycle = _normal_lifecycle(stage_refs)
    if lifecycle != normal_lifecycle:
        raise TurnLifecycleError(
            f"lifecycle {lifecycle} cannot advance; expected {normal_lifecycle}"
        )
    if len(stage_refs) == len(BEHAVIOR_TURN_STAGE_ORDER):
        raise TurnLifecycleError("turn has no remaining canonical stage")
    return BEHAVIOR_TURN_STAGE_ORDER[len(stage_refs)]


def lifecycle_after(stage: BehaviorTurnStage) -> CharacterTurnLifecycle:
    return _TRANSITION_BY_STAGE[stage][1]


class CharacterTurnLifecycleTransition(BaseModel):
    """An immutable non-stage terminal or recovery transition."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    from_lifecycle: CharacterTurnLifecycle
    to_lifecycle: CharacterTurnLifecycle
    transition_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    producer_ts: int = Field(ge=0)
    payload: Mapping[str, JsonValue] = Field(default_factory=dict)

    @field_validator("payload", mode="after")
    @classmethod
    def freeze_payload(cls, payload: Mapping[str, JsonValue]) -> Mapping[str, JsonValue]:
        return MappingProxyType(dict(payload))


class CharacterTurnReceipt(BaseModel):
    """A separately typed actor-private continuity checkpoint/receipt."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    valid_at: int = Field(ge=0)
    lifecycle: CharacterTurnLifecycle
    producer_ts: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1)
    input_revision_vector: Mapping[str, int]
    memory_revision_vector: Mapping[str, int]
    policy_revision: str = Field(min_length=1)
    snapshot_revision: int = Field(ge=0)
    receipt_ref: str | None = Field(default=None, min_length=1)
    checkpoint_ref: str | None = Field(default=None, min_length=1)

    @field_validator("input_revision_vector", "memory_revision_vector", mode="after")
    @classmethod
    def freeze_revision_vector(cls, vector: Mapping[str, int]) -> Mapping[str, int]:
        if any(revision < 0 for revision in vector.values()):
            raise ValueError("revision vector entries must be non-negative")
        return MappingProxyType(dict(vector))


class CharacterTurnContext(BaseModel):
    """Immutable identity, persistence pins, and lifecycle state for one turn."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    source_event_ref: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    lifecycle: CharacterTurnLifecycle
    stage_refs: Mapping[str, str] = Field(default_factory=dict)
    stage_idempotency_keys: Mapping[str, str] = Field(default_factory=dict)
    stage_events: Mapping[str, CharacterTurnStageEvent] = Field(default_factory=dict)
    lifecycle_transitions: tuple[CharacterTurnLifecycleTransition, ...] = ()
    input_revision_vector: Mapping[str, int]
    memory_revision_vector: Mapping[str, int]
    policy_revision: str = Field(min_length=1)
    snapshot_revision: int = Field(ge=0)
    branch_id: str | None = Field(default=None, min_length=1)
    valid_at: int = Field(ge=0)
    producer_ts: int = Field(ge=0)

    @field_validator("stage_refs", "stage_idempotency_keys", "stage_events", mode="after")
    @classmethod
    def freeze_stage_mappings(cls, mapping: Mapping[str, object]) -> Mapping[str, object]:
        return MappingProxyType(dict(mapping))

    @field_validator("input_revision_vector", "memory_revision_vector", mode="after")
    @classmethod
    def freeze_revision_vector(cls, vector: Mapping[str, int]) -> Mapping[str, int]:
        if any(revision < 0 for revision in vector.values()):
            raise ValueError("revision vector entries must be non-negative")
        return MappingProxyType(dict(vector))

    @model_validator(mode="after")
    def validate_stage_state(self) -> "CharacterTurnContext":
        if tuple(self.stage_refs) != tuple(self.stage_idempotency_keys):
            raise ValueError("stage refs and idempotency keys must have matching stages")
        if any(stage not in self.stage_refs for stage in self.stage_events):
            raise ValueError("stage events require matching stage refs")
        for stage, ref in self.stage_refs.items():
            if stage not in _TRANSITION_BY_STAGE or not ref:
                raise ValueError("stage refs must use known stages with non-empty refs")
        if any(not key for key in self.stage_idempotency_keys.values()):
            raise ValueError("stage idempotency keys must be non-empty")
        for stage, event in self.stage_events.items():
            if (
                event.turn_id != self.turn_id or event.actor_id != self.actor_id
                or event.causation_id != self.causation_id
                or event.correlation_id != self.correlation_id or event.stage != stage
                or event.stage_ref != self.stage_refs[stage]
                or event.idempotency_key != self.stage_idempotency_keys[stage]
                or event.valid_at != self.valid_at
                or event.input_revision_vector != self.input_revision_vector
                or event.memory_revision_vector != self.memory_revision_vector
                or event.policy_revision != self.policy_revision
                or event.snapshot_revision != self.snapshot_revision
                or event.branch_id != self.branch_id
            ):
                raise ValueError("canonical stage event must match its turn context")
        expected_lifecycle = _normal_lifecycle(self.stage_refs)
        for transition in self.lifecycle_transitions:
            if transition.from_lifecycle != expected_lifecycle or (
                transition.from_lifecycle, transition.to_lifecycle
            ) not in _TERMINAL_LIFECYCLE_TRANSITIONS:
                raise ValueError("invalid terminal lifecycle transition")
            expected_lifecycle = transition.to_lifecycle
        if self.lifecycle != expected_lifecycle:
            raise ValueError(f"turn lifecycle must be {expected_lifecycle}")
        return self

    @classmethod
    def begin(
        cls, actor_id: str, source_event_ref: str, producer_ts: int, *,
        causation_id: str, correlation_id: str,
        input_revision_vector: Mapping[str, int], memory_revision_vector: Mapping[str, int],
        policy_revision: str, snapshot_revision: int, branch_id: str | None = None,
    ) -> "CharacterTurnContext":
        return cls(
            turn_id=f"turn:{actor_id}:{source_event_ref}", actor_id=actor_id,
            source_event_ref=source_event_ref, causation_id=causation_id,
            correlation_id=correlation_id, lifecycle="prepared",
            input_revision_vector=input_revision_vector,
            memory_revision_vector=memory_revision_vector,
            policy_revision=policy_revision, snapshot_revision=snapshot_revision,
            branch_id=branch_id, valid_at=producer_ts, producer_ts=producer_ts,
        )

    def advance(
        self, stage: BehaviorTurnStage, *, stage_ref: str,
        idempotency_key: str, producer_ts: int,
    ) -> "CharacterTurnContext":
        if producer_ts < 0:
            raise TurnLifecycleError("producer_ts must be non-negative")
        if not stage_ref or not idempotency_key:
            raise TurnLifecycleError("stage ref and idempotency key are required")
        if stage in self.stage_refs:
            if self.stage_refs[stage] != stage_ref or self.stage_idempotency_keys[stage] != idempotency_key:
                raise TurnLifecycleError("stage idempotency payload mismatch")
            return self
        expected_stage = expected_next_stage(self.stage_refs, self.lifecycle)
        if stage != expected_stage:
            raise TurnLifecycleError(f"expected {expected_stage}, got {stage}")
        return self.model_copy(update={
            "stage_refs": MappingProxyType({**self.stage_refs, stage: stage_ref}),
            "stage_idempotency_keys": MappingProxyType({
                **self.stage_idempotency_keys, stage: idempotency_key
            }),
            "lifecycle": lifecycle_after(stage),
        })

    def stage_event(
        self, stage: BehaviorTurnStage, *, stage_ref: str, idempotency_key: str,
        producer_ts: int, outcome: BehaviorTurnOutcome = "recorded",
        payload: Mapping[str, JsonValue] | None = None,
    ) -> tuple["CharacterTurnContext", CharacterTurnStageEvent]:
        """Advance and atomically freeze the corresponding canonical event."""
        if self.branch_id is None:
            raise TurnLifecycleError("canonical stage events require a branch id")
        advanced = self.advance(
            stage, stage_ref=stage_ref, idempotency_key=idempotency_key,
            producer_ts=producer_ts,
        )
        candidate = CharacterTurnStageEvent(
            turn_id=advanced.turn_id, actor_id=advanced.actor_id,
            correlation_id=advanced.correlation_id, causation_id=advanced.causation_id,
            branch_id=self.branch_id, valid_at=advanced.valid_at, stage=stage,
            stage_ref=stage_ref, idempotency_key=idempotency_key, producer_ts=producer_ts,
            input_revision_vector=advanced.input_revision_vector,
            memory_revision_vector=advanced.memory_revision_vector,
            policy_revision=advanced.policy_revision,
            snapshot_revision=advanced.snapshot_revision, outcome=outcome,
            payload=payload or {},
        )
        existing = advanced.stage_events.get(stage)
        if existing is not None:
            if existing != candidate:
                raise TurnLifecycleError("stage idempotency payload mismatch")
            return advanced, existing
        return advanced.model_copy(update={
            "stage_events": MappingProxyType({**advanced.stage_events, stage: candidate})
        }), candidate

    def transition(
        self, lifecycle: CharacterTurnLifecycle, *, transition_ref: str,
        idempotency_key: str, producer_ts: int, payload: Mapping[str, JsonValue],
    ) -> "CharacterTurnContext":
        for existing in self.lifecycle_transitions:
            if (
                existing.transition_ref == transition_ref
                and existing.idempotency_key == idempotency_key
            ):
                if (
                    existing.to_lifecycle == lifecycle
                    and existing.producer_ts == producer_ts
                    and existing.payload == payload
                ):
                    return self
                raise TurnLifecycleError("transition idempotency payload mismatch")
            if (
                existing.transition_ref == transition_ref
                or existing.idempotency_key == idempotency_key
            ):
                raise TurnLifecycleError("transition idempotency payload mismatch")
        candidate = CharacterTurnLifecycleTransition(
            from_lifecycle=self.lifecycle, to_lifecycle=lifecycle,
            transition_ref=transition_ref, idempotency_key=idempotency_key,
            producer_ts=producer_ts, payload=payload,
        )
        if self.lifecycle_transitions and self.lifecycle_transitions[-1] == candidate:
            return self
        if (self.lifecycle, lifecycle) not in _TERMINAL_LIFECYCLE_TRANSITIONS:
            raise TurnLifecycleError(f"cannot transition from {self.lifecycle} to {lifecycle}")
        return self.model_copy(update={
            "lifecycle": lifecycle,
            "lifecycle_transitions": (*self.lifecycle_transitions, candidate),
        })

    def receipt(
        self, *, producer_ts: int, idempotency_key: str,
        receipt_ref: str | None = None, checkpoint_ref: str | None = None,
    ) -> CharacterTurnReceipt:
        if self.branch_id is None:
            raise TurnLifecycleError("actor-private receipts require a branch id")
        return CharacterTurnReceipt(
            turn_id=self.turn_id, actor_id=self.actor_id,
            causation_id=self.causation_id, correlation_id=self.correlation_id,
            branch_id=self.branch_id, valid_at=self.valid_at, lifecycle=self.lifecycle,
            producer_ts=producer_ts, idempotency_key=idempotency_key,
            input_revision_vector=self.input_revision_vector,
            memory_revision_vector=self.memory_revision_vector,
            policy_revision=self.policy_revision,
            snapshot_revision=self.snapshot_revision, receipt_ref=receipt_ref,
            checkpoint_ref=checkpoint_ref,
        )


__all__ = [
    "CHARACTER_TURN_STAGE_TRANSITIONS", "CharacterTurnContext",
    "CharacterTurnLifecycle", "CharacterTurnLifecycleTransition",
    "CharacterTurnReceipt", "CharacterTurnStageEvent", "TurnLifecycleError",
    "expected_next_stage", "lifecycle_after",
]
