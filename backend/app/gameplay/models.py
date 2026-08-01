from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IdempotencyStatus = Literal["new_commit", "duplicate_replayed", "rejected"]
OutboxDeliveryState = Literal["pending", "retryable", "delivered"]


class StrictGameplayModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GameplayFailure(StrictGameplayModel):
    error_code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    failed_stage: str = Field(min_length=1)
    retriable: bool = False
    expected_revision: int | None = None
    actual_revision: int | None = None
    stream_id: str | None = None


class ProjectionRefreshHint(StrictGameplayModel):
    projection_id: str = Field(min_length=1)
    stream_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class IdempotencyRecord(StrictGameplayModel):
    principal_ref: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    payload_digest: str = Field(min_length=1)


class GameplayEvent(StrictGameplayModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    schema_version: int = Field(ge=1)
    stream_id: str = Field(min_length=1)
    stream_revision: int = Field(ge=0)
    global_sequence: int = Field(ge=0)
    transaction_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    visibility_policy: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class GameplayOutboxEntry(StrictGameplayModel):
    outbox_id: str = Field(min_length=1)
    transaction_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    global_sequence: int = Field(ge=0)
    topic: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    payload_projection: dict[str, Any] = Field(default_factory=dict)
    delivery_state: OutboxDeliveryState = "pending"
    attempt_count: int = Field(default=0, ge=0)
    last_error: str | None = None

    @model_validator(mode="after")
    def reject_projection_failure_sentinel(self) -> "GameplayOutboxEntry":
        if "_projection_error" in self.payload_projection:
            raise ValueError("outbox_projection_failed")
        return self


class AtomicEventBatch(StrictGameplayModel):
    transaction_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    expected_stream_revisions: dict[str, int] = Field(default_factory=dict)
    pinned_revisions: dict[str, int] = Field(default_factory=dict)
    events: list[GameplayEvent] = Field(min_length=1)
    idempotency_record: IdempotencyRecord
    outbox_entries: list[GameplayOutboxEntry] = Field(default_factory=list)
    result_digest: str = Field(min_length=1)
    projection_refresh_hints: list[ProjectionRefreshHint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_batch_identity(self) -> "AtomicEventBatch":
        event_ids = {event.event_id for event in self.events}
        for event in self.events:
            if event.transaction_id != self.transaction_id:
                raise ValueError("event transaction_id must match batch")
            if event.command_id != self.command_id:
                raise ValueError("event command_id must match batch")
        for entry in self.outbox_entries:
            if entry.transaction_id != self.transaction_id:
                raise ValueError("outbox transaction_id must match batch")
            if entry.event_id not in event_ids:
                raise ValueError("outbox entry must reference a batch event")
        return self


class AppendBatchResult(StrictGameplayModel):
    committed: bool
    transaction_id: str
    command_id: str
    committed_event_ids: list[str] = Field(default_factory=list)
    resulting_stream_revisions: dict[str, int] = Field(default_factory=dict)
    global_sequence_range: tuple[int, int] | None = None
    idempotency_status: IdempotencyStatus
    failure: GameplayFailure | None = None
    projection_refresh_hints: list[ProjectionRefreshHint] = Field(default_factory=list)


class DispatchResult(StrictGameplayModel):
    published_count: int = 0
    failed_count: int = 0
    delivered_outbox_ids: list[str] = Field(default_factory=list)
    failed_outbox_ids: list[str] = Field(default_factory=list)


class ProjectionCheckpoint(StrictGameplayModel):
    checkpoint_id: str = Field(min_length=1)
    projector_id: str = Field(min_length=1)
    projector_version: str = Field(min_length=1)
    projection_schema_version: int = Field(ge=1)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    last_global_sequence: int = 0
    state: dict[str, Any] = Field(default_factory=dict)
    applied_event_ids: list[str] = Field(default_factory=list)
    projection_hash: str = Field(min_length=1)


class ReplayResult(StrictGameplayModel):
    succeeded: bool
    projector_id: str
    projector_version: str
    projection_hash: str = ""
    state: dict[str, Any] = Field(default_factory=dict)
    source_revision_vector: dict[str, int] = Field(default_factory=dict)
    last_global_sequence: int = 0
    applied_event_ids: list[str] = Field(default_factory=list)
    applied_event_count: int = 0
    failure: GameplayFailure | None = None
