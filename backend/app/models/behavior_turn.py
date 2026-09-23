from __future__ import annotations

from contextvars import ContextVar
from types import MappingProxyType
from typing import Any, Literal, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    field_validator,
    model_validator,
)

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    HeavenlyGraphScope,
)

BehaviorTurnStage = Literal[
    "context",
    "interpretation",
    "goal",
    "intent",
    "execution",
    "settlement",
    "evaluation",
    "policy",
]
BehaviorTurnOutcome = Literal[
    "recorded",
    "accepted",
    "committed",
    "rejected",
    "failed",
    "skipped",
]

_legacy_reader_admission: ContextVar[bool] = ContextVar(
    "legacy_behavior_turn_reader_admission", default=False
)

BEHAVIOR_TURN_STAGE_TRANSITIONS: tuple[
    tuple[BehaviorTurnStage, str, str], ...
] = (
    ("context", "prepared", "running"),
    ("interpretation", "running", "running"),
    ("goal", "running", "running"),
    ("intent", "running", "running"),
    ("execution", "running", "awaiting_settlement"),
    ("settlement", "awaiting_settlement", "settled"),
    ("evaluation", "settled", "evaluated"),
    ("policy", "evaluated", "committed"),
)

BEHAVIOR_TURN_STAGE_ORDER: tuple[BehaviorTurnStage, ...] = tuple(
    stage for stage, _, _ in BEHAVIOR_TURN_STAGE_TRANSITIONS
)


class BehaviorTurnStageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    stage: BehaviorTurnStage
    outcome: BehaviorTurnOutcome = "recorded"
    source_refs: tuple[str, ...] = Field(default_factory=tuple)
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class CharacterTurnStageEvent(BaseModel):
    """Canonical actor-private stage record before graph projection."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    turn_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    branch_id: str = Field(min_length=1)
    valid_at: int = Field(ge=0)
    stage: BehaviorTurnStage
    stage_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    producer_ts: int = Field(ge=0)
    input_revision_vector: Mapping[str, int]
    memory_revision_vector: Mapping[str, int]
    policy_revision: str = Field(min_length=1)
    snapshot_revision: int = Field(ge=0)
    outcome: BehaviorTurnOutcome = "recorded"
    payload: Mapping[str, JsonValue] = Field(default_factory=dict)

    @field_validator("input_revision_vector", "memory_revision_vector", mode="after")
    @classmethod
    def freeze_revision_vector(
        cls, revision_vector: Mapping[str, int]
    ) -> Mapping[str, int]:
        if any(revision < 0 for revision in revision_vector.values()):
            raise ValueError("revision vector entries must be non-negative")
        return MappingProxyType(dict(revision_vector))

    @field_validator("payload", mode="after")
    @classmethod
    def freeze_canonical_payload(
        cls, payload: Mapping[str, JsonValue]
    ) -> Mapping[str, JsonValue]:
        return MappingProxyType(dict(payload))


class BehaviorTurnRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    turn_id: str = Field(min_length=1)
    scope: HeavenlyGraphScope
    valid_at: int = Field(ge=0)
    recorded_at: int = Field(ge=0)
    policy_revision: str = Field(min_length=1)
    source_revision_vector: GraphRevisionVector
    scope_digest: str = Field(min_length=1)
    provenance: GraphProvenance
    transaction_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    stages: tuple[BehaviorTurnStageRecord, ...] = Field(min_length=1)
    record_origin: Literal["canonical_stage_events", "legacy_reader"] | None = None
    legacy_reader_ref: str | None = Field(default=None, min_length=1)
    canonical_stage_events: tuple[CharacterTurnStageEvent, ...] = Field(
        default_factory=tuple
    )
    branch_id: str | None = Field(default=None, min_length=1)
    input_revision_vector: Mapping[str, int] | None = None
    memory_revision_vector: Mapping[str, int] | None = None
    snapshot_revision: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_actor_scope(self) -> "BehaviorTurnRecordRequest":
        if self.record_origin is None:
            raise ValueError("record origin is required")
        if (
            self.scope.graph_namespace == "actor_private"
            and self.provenance.actor_id != self.scope.owner_actor_id
        ):
            raise ValueError("actor-private turn provenance must match scope owner")
        if self.record_origin == "legacy_reader":
            if not self.legacy_reader_ref:
                raise ValueError("legacy records require an explicit legacy reader ref")
            if not _legacy_reader_admission.get():
                raise ValueError("legacy records require the explicit legacy reader")
            if self.canonical_stage_events:
                raise ValueError("legacy records cannot carry canonical stage events")
            return self
        if self.legacy_reader_ref:
            raise ValueError("canonical records cannot carry a legacy reader ref")
        if not self.canonical_stage_events:
            raise ValueError("canonical records require canonical stage events")
        if (
            self.branch_id is None
            or self.input_revision_vector is None
            or self.memory_revision_vector is None
            or self.snapshot_revision is None
        ):
            raise ValueError("canonical records require branch and revision pins")
        if self.branch_id != self.scope.story_branch_id:
            raise ValueError("canonical stage branch must match request scope")
        expected_stages = tuple(
            BehaviorTurnStageRecord(
                stage=event.stage,
                outcome=event.outcome,
                source_refs=(event.stage_ref,),
                payload=event.payload,
            )
            for event in self.canonical_stage_events
        )
        if self.stages != expected_stages:
            raise ValueError("canonical records must project their canonical stages")
        actual_stages = tuple(event.stage for event in self.canonical_stage_events)
        if actual_stages != BEHAVIOR_TURN_STAGE_ORDER[: len(actual_stages)]:
            raise ValueError("canonical stage events must follow contiguous canonical order")
        for event in self.canonical_stage_events:
            if (
                event.turn_id != self.turn_id
                or event.actor_id != self.provenance.actor_id
                or event.actor_id != self.scope.owner_actor_id
                or event.correlation_id != self.provenance.correlation_id
                or event.causation_id != self.provenance.causation_id
            ):
                raise ValueError(
                    "canonical stage identity must match request scope and provenance"
                )
            if event.branch_id != self.branch_id:
                raise ValueError("canonical stage branch must match request scope")
            if event.valid_at != self.valid_at:
                raise ValueError("canonical stage valid time must match request")
            if event.input_revision_vector != self.input_revision_vector:
                raise ValueError("canonical stage input revision must match request")
            if event.memory_revision_vector != self.memory_revision_vector:
                raise ValueError("canonical stage memory revision must match request")
            if event.policy_revision != self.policy_revision:
                raise ValueError("canonical stage policy revision must match request")
            if event.snapshot_revision != self.snapshot_revision:
                raise ValueError("canonical stage snapshot revision must match request")
        return self

    @classmethod
    def from_canonical_stage_events(
        cls,
        *,
        stage_events: tuple["CharacterTurnStageEvent", ...],
        **request_fields: Any,
    ) -> "BehaviorTurnRecordRequest":
        """Validate canonical identity before creating compact graph stages.

        The graph-stage payload deliberately has no copied identity fields:
        `BehaviorTurnRecorder` inherits the validated request identity for every
        node and relation it projects.
        """
        request_fields.pop("stages", None)
        return cls(
            **request_fields,
            record_origin="canonical_stage_events",
            canonical_stage_events=stage_events,
            stages=tuple(
                BehaviorTurnStageRecord(
                    stage=event.stage,
                    outcome=event.outcome,
                    source_refs=(event.stage_ref,),
                    payload=event.payload,
                )
                for event in stage_events
            ),
        )

    @classmethod
    def from_legacy_projection(
        cls, *, legacy_reader_ref: str, **request_fields: Any
    ) -> "BehaviorTurnRecordRequest":
        """Read historical compact projections without treating them as live turns."""
        token = _legacy_reader_admission.set(True)
        try:
            return cls(
                **request_fields,
                record_origin="legacy_reader",
                legacy_reader_ref=legacy_reader_ref,
            )
        finally:
            _legacy_reader_admission.reset(token)


__all__ = [
    "BEHAVIOR_TURN_STAGE_ORDER",
    "BEHAVIOR_TURN_STAGE_TRANSITIONS",
    "BehaviorTurnOutcome",
    "BehaviorTurnRecordRequest",
    "BehaviorTurnStage",
    "BehaviorTurnStageRecord",
    "CharacterTurnStageEvent",
]
