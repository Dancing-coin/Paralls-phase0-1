from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


_IDENTITY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,255}$"


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

    policy_id: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)
    actor_id: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)
    source_turn_id: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)
    branch_id: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)
    valid_at: int = Field(ge=0)
    causation_id: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)
    correlation_id: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)
    source_revision: int = Field(ge=0)
    policy_type: BehaviorPolicyType
    failed_intent: str = ""
    hypothesis: str
    status: BehaviorPolicyStatus = "candidate"
    created_at: int
    expires_at: int
    max_consumptions: int = Field(ge=1)
    consumed_count: int = Field(default=0, ge=0)
    consumed_turn_ids: list[str] = Field(default_factory=list)
    consumption_links: dict[str, dict[str, str]] = Field(default_factory=dict)
    merged_idempotency_keys: list[str] = Field(default_factory=list)
    merged_idempotency_digests: dict[str, str] = Field(default_factory=dict)
    failure_window: int = Field(default=0, ge=0)
    failure_count: int = Field(default=1, ge=0)
    policy_revision: int = Field(default=1, ge=1)
    transition_revision: int = Field(default=0, ge=0)
    supersedes_policy_id: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    idempotency_key: str = Field(min_length=1, max_length=256, pattern=_IDENTITY_PATTERN)

    @model_validator(mode="after")
    def _valid_lifecycle_shape(self) -> "BehaviorPolicyRecord":
        if self.expires_at < self.created_at:
            raise ValueError("behavior_policy_expiry_precedes_creation")
        if self.consumed_count != len(self.consumed_turn_ids):
            raise ValueError("behavior_policy_consumption_count_mismatch")
        if len(set(self.consumed_turn_ids)) != len(self.consumed_turn_ids):
            raise ValueError("behavior_policy_duplicate_turn_consumption")
        if set(self.consumption_links) - set(self.consumed_turn_ids):
            raise ValueError("behavior_policy_consumption_link_mismatch")
        if any(not key or not re.fullmatch(_IDENTITY_PATTERN, key) for key in self.merged_idempotency_keys):
            raise ValueError("behavior_policy_invalid_merged_idempotency_key")
        if len(set(self.merged_idempotency_keys)) != len(self.merged_idempotency_keys):
            raise ValueError("behavior_policy_duplicate_merged_idempotency_key")
        if set(self.merged_idempotency_digests) - set(self.merged_idempotency_keys):
            raise ValueError("behavior_policy_merged_idempotency_digest_mismatch")
        if any(
            not key or not re.fullmatch(_IDENTITY_PATTERN, key) or not digest
            for key, digest in self.merged_idempotency_digests.items()
        ):
            raise ValueError("behavior_policy_invalid_merged_idempotency_digest")
        for turn_id, link in self.consumption_links.items():
            if not turn_id or not re.fullmatch(_IDENTITY_PATTERN, turn_id):
                raise ValueError("behavior_policy_invalid_consumed_turn_id")
            if not isinstance(link, dict) or set(link) != {"branch_id", "causation_id", "correlation_id"}:
                raise ValueError("behavior_policy_consumption_link_invalid")
            if any(not value or not re.fullmatch(_IDENTITY_PATTERN, value) for value in link.values()):
                raise ValueError("behavior_policy_consumption_link_invalid")
        if self.valid_at < self.created_at:
            raise ValueError("behavior_policy_valid_time_precedes_creation")
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
