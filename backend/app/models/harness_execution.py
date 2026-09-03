from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExecutionPhase = Literal[
    "created",
    "running",
    "waiting",
    "recovering",
    "committed",
    "failed",
    "aborted",
]
FailureKind = Literal[
    "transient",
    "invalid_input",
    "permission_denied",
    "constraint_conflict",
    "dependency_missing",
    "stale_revision",
    "delivery_failed",
    "unknown",
]
RecoveryAction = Literal[
    "retry",
    "repair_input",
    "request_approval",
    "replan",
    "wait_dependency",
    "refresh_revision",
    "abort",
]
CapabilityState = Literal["issued", "consumed", "revoked", "expired"]


class StrictHarnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FailureDisposition(StrictHarnessModel):
    kind: FailureKind
    recovery_action: RecoveryAction
    retryable: bool
    max_attempts: int = Field(ge=0)
    terminal: bool


class ExecutionEnvelope(StrictHarnessModel):
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str = ""
    policy_revision: str = ""
    authority_revision: str = ""
    checkpoint_ref: str = ""
    phase: ExecutionPhase = "created"
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=0)
    revision: int = Field(default=0, ge=0)
    failure: FailureDisposition | None = None


class TaskTraceRecord(StrictHarnessModel):
    sequence: int = Field(ge=1)
    task_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    causation_id: str = ""
    stage: str = Field(min_length=1)
    status: str = Field(min_length=1)
    producer_ts: int = Field(ge=0)
    metadata: dict[str, object] = Field(default_factory=dict)


class CapabilityGrant(StrictHarnessModel):
    grant_id: str = Field(min_length=1)
    principal_ref: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    phase: str = Field(min_length=1)
    policy_revision: str = Field(min_length=1)
    expires_at: int = Field(ge=0)
    nonce: str = Field(min_length=1)
    state: CapabilityState = "issued"


_FAILURE_POLICIES: dict[FailureKind, FailureDisposition] = {
    "transient": FailureDisposition(
        kind="transient",
        recovery_action="retry",
        retryable=True,
        max_attempts=3,
        terminal=False,
    ),
    "invalid_input": FailureDisposition(
        kind="invalid_input",
        recovery_action="repair_input",
        retryable=False,
        max_attempts=0,
        terminal=True,
    ),
    "permission_denied": FailureDisposition(
        kind="permission_denied",
        recovery_action="request_approval",
        retryable=False,
        max_attempts=0,
        terminal=True,
    ),
    "constraint_conflict": FailureDisposition(
        kind="constraint_conflict",
        recovery_action="replan",
        retryable=False,
        max_attempts=0,
        terminal=False,
    ),
    "dependency_missing": FailureDisposition(
        kind="dependency_missing",
        recovery_action="wait_dependency",
        retryable=False,
        max_attempts=0,
        terminal=False,
    ),
    "stale_revision": FailureDisposition(
        kind="stale_revision",
        recovery_action="refresh_revision",
        retryable=False,
        max_attempts=0,
        terminal=False,
    ),
    "delivery_failed": FailureDisposition(
        kind="delivery_failed",
        recovery_action="retry",
        retryable=True,
        max_attempts=3,
        terminal=False,
    ),
    "unknown": FailureDisposition(
        kind="unknown",
        recovery_action="abort",
        retryable=False,
        max_attempts=0,
        terminal=True,
    ),
}


def classify_failure(kind: FailureKind) -> FailureDisposition:
    return _FAILURE_POLICIES[kind].model_copy(deep=True)


__all__ = [
    "ExecutionEnvelope",
    "ExecutionPhase",
    "CapabilityGrant",
    "FailureDisposition",
    "FailureKind",
    "RecoveryAction",
    "TaskTraceRecord",
    "classify_failure",
]
