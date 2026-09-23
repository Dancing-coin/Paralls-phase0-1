from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


BehaviorPolicyStatus = Literal[
    "candidate",
    "accepted",
    "applied",
    "expired",
    "superseded",
    "rolled_back",
    "rejected",
]
BehaviorPolicyType = Literal["recovery", "recall", "skill_calibration", "cadence"]


class BehaviorPolicyRecord(BaseModel):
    """Actor-private, forward-looking strategy state; never world truth."""

    model_config = ConfigDict(extra="forbid")

    policy_id: str
    actor_id: str
    source_turn_id: str
    policy_type: BehaviorPolicyType
    failed_intent: str = ""
    hypothesis: str
    status: BehaviorPolicyStatus = "candidate"
    created_at: int
    expires_at: int
    max_consumptions: int = Field(ge=1)
    consumed_count: int = Field(default=0, ge=0)
    consumed_turn_ids: list[str] = Field(default_factory=list)
    failure_window: int = Field(default=0, ge=0)
    failure_count: int = Field(default=1, ge=0)
    policy_revision: int = Field(default=1, ge=1)
    supersedes_policy_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    idempotency_key: str

    @model_validator(mode="after")
    def _valid_lifecycle_shape(self) -> "BehaviorPolicyRecord":
        if self.expires_at < self.created_at:
            raise ValueError("behavior_policy_expiry_precedes_creation")
        if self.consumed_count != len(self.consumed_turn_ids):
            raise ValueError("behavior_policy_consumption_count_mismatch")
        if len(set(self.consumed_turn_ids)) != len(self.consumed_turn_ids):
            raise ValueError("behavior_policy_duplicate_turn_consumption")
        return self


class BehaviorPolicyConsumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record: BehaviorPolicyRecord
    applied: bool
    replayed: bool = False
    reason: str = ""


__all__ = [
    "BehaviorPolicyConsumption",
    "BehaviorPolicyRecord",
    "BehaviorPolicyStatus",
    "BehaviorPolicyType",
]
