from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryFactClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope_ref: str = Field(min_length=1)
    subject_ref: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    valid_at: int
    source_ref: str = Field(min_length=1)


def compare_memory_claims(
    left: MemoryFactClaim | None, right: MemoryFactClaim | None
) -> Literal["consistent", "conflicted", "not_comparable"]:
    if left is None or right is None:
        return "not_comparable"
    if (left.scope_ref, left.subject_ref, left.predicate, left.valid_at) != (
        right.scope_ref, right.subject_ref, right.predicate, right.valid_at
    ):
        return "not_comparable"
    return "consistent" if left.value == right.value else "conflicted"


def memory_claim_key(claim: MemoryFactClaim) -> str:
    return f"fact:{claim.scope_ref}:{claim.subject_ref}:{claim.predicate}"


class MemorySourceRecord(BaseModel):
    """权威 owner 按来源返回的内容与版本，不能由修复申请者提供。"""
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim: MemoryFactClaim
    revision: int = Field(ge=0, strict=True)


class MemoryConsistencyResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_id: str
    producer_ts: int = Field(ge=0, strict=True)
    status: Literal["no_conflicts", "policy_skipped", "rate_limited", "truth_wins", "verification_required"]
    conflict_refs: tuple[str, ...] = ()
    verification_request_refs: tuple[str, ...] = ()
    next_check_at: int | None = None


class MemoryCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    target_memory_refs: tuple[str, ...] = Field(min_length=1, max_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1, max_length=4)
    reason: str = Field(min_length=1, max_length=500)
    expected_character_revision: int = Field(ge=0, strict=True)
    source_revision_vector: dict[str, int]
    requested_at: int = Field(ge=0, strict=True)
    expires_at: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def validate_sources(self):
        if set(self.source_refs) != set(self.source_revision_vector):
            raise ValueError("source revision vector must cover exactly the source refs")
        if any(not ref.strip() for ref in (*self.source_refs, *self.target_memory_refs)):
            raise ValueError("memory and source refs must be nonempty")
        if len(set(self.source_refs)) != len(self.source_refs):
            raise ValueError("source refs must be unique")
        if any(type(value) is not int or value < 0 for value in self.source_revision_vector.values()):
            raise ValueError("source revisions must be nonnegative integers")
        return self


class MemoryCorrectionReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    actor_id: str
    status: Literal["applied", "rejected"]
    reason: str = ""
    before_revision: int
    after_revision: int
    applied_memory_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()
