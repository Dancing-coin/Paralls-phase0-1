from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

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

BEHAVIOR_TURN_STAGE_ORDER: tuple[BehaviorTurnStage, ...] = (
    "context",
    "interpretation",
    "goal",
    "intent",
    "execution",
    "settlement",
    "evaluation",
    "policy",
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


__all__ = [
    "BEHAVIOR_TURN_STAGE_ORDER",
    "BehaviorTurnOutcome",
    "BehaviorTurnRecordRequest",
    "BehaviorTurnStage",
    "BehaviorTurnStageRecord",
]
