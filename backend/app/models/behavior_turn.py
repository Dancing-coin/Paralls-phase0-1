from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from app.models.siming_heavenly_graph import (
    GraphProvenance,
    GraphRevisionVector,
    HeavenlyGraphScope,
)

if TYPE_CHECKING:
    from app.character_agent.models.turn_context import CharacterTurnStageEvent


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


class BehaviorTurnRecordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

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

    @model_validator(mode="after")
    def validate_actor_scope(self) -> "BehaviorTurnRecordRequest":
        if (
            self.scope.graph_namespace == "actor_private"
            and self.provenance.actor_id != self.scope.owner_actor_id
        ):
            raise ValueError("actor-private turn provenance must match scope owner")
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
        if not stage_events:
            raise ValueError("canonical stage events are required")
        turn_id = str(request_fields.get("turn_id", ""))
        scope = request_fields.get("scope")
        provenance = request_fields.get("provenance")
        expected_actor_id = getattr(provenance, "actor_id", "")
        expected_correlation_id = getattr(provenance, "correlation_id", "")
        scope_actor_id = getattr(scope, "owner_actor_id", "")

        for event in stage_events:
            if (
                event.turn_id != turn_id
                or event.actor_id != expected_actor_id
                or event.correlation_id != expected_correlation_id
                or (
                    getattr(scope, "graph_namespace", "") == "actor_private"
                    and event.actor_id != scope_actor_id
                )
            ):
                raise ValueError(
                    "canonical stage identity must match request scope and provenance"
                )
            if event.causation_id != getattr(provenance, "causation_id", ""):
                raise ValueError(
                    "canonical stage identity must match request scope and provenance"
                )

        actual_stages = tuple(event.stage for event in stage_events)
        if actual_stages != BEHAVIOR_TURN_STAGE_ORDER[: len(actual_stages)]:
            raise ValueError("canonical stage events must follow contiguous canonical order")
        return cls(
            **request_fields,
            stages=tuple(
                BehaviorTurnStageRecord(
                    stage=event.stage,
                    outcome=event.outcome,
                    source_refs=(event.stage_ref,),
                    payload={},
                )
                for event in stage_events
            ),
        )

    @classmethod
    def from_legacy_projection(
        cls, **request_fields: Any
    ) -> "BehaviorTurnRecordRequest":
        """Read historical compact projections without treating them as live turns."""
        return cls(**request_fields)


__all__ = [
    "BEHAVIOR_TURN_STAGE_ORDER",
    "BEHAVIOR_TURN_STAGE_TRANSITIONS",
    "BehaviorTurnOutcome",
    "BehaviorTurnRecordRequest",
    "BehaviorTurnStage",
    "BehaviorTurnStageRecord",
]
