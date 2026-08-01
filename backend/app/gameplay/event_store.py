from __future__ import annotations

from collections import defaultdict
from typing import Any

from pydantic import ValidationError

from app.gameplay.models import (
    AppendBatchResult,
    AtomicEventBatch,
    GameplayEvent,
    GameplayFailure,
    GameplayOutboxEntry,
    IdempotencyRecord,
)


def _failure(
    error_code: str,
    *,
    message: str,
    failed_stage: str,
    retriable: bool = False,
    expected_revision: int | None = None,
    actual_revision: int | None = None,
    stream_id: str | None = None,
) -> GameplayFailure:
    return GameplayFailure(
        error_code=error_code,
        message=message,
        failed_stage=failed_stage,
        retriable=retriable,
        expected_revision=expected_revision,
        actual_revision=actual_revision,
        stream_id=stream_id,
    )


def _empty_result(
    *,
    transaction_id: str,
    command_id: str,
    error_code: str,
    message: str,
    failed_stage: str,
    retriable: bool = False,
    expected_revision: int | None = None,
    actual_revision: int | None = None,
    stream_id: str | None = None,
) -> AppendBatchResult:
    return AppendBatchResult(
        committed=False,
        transaction_id=transaction_id,
        command_id=command_id,
        idempotency_status="rejected",
        failure=_failure(
            error_code,
            message=message,
            failed_stage=failed_stage,
            retriable=retriable,
            expected_revision=expected_revision,
            actual_revision=actual_revision,
            stream_id=stream_id,
        ),
    )


class GameplayEventStore:
    """In-memory authority ledger for the first Gameplay Foundation closure."""

    def __init__(self) -> None:
        self._events: list[GameplayEvent] = []
        self._events_by_id: dict[str, GameplayEvent] = {}
        self._transactions: list[AtomicEventBatch] = []
        self._transaction_results: dict[str, AppendBatchResult] = {}
        self._stream_heads: dict[str, int] = defaultdict(int)
        self._idempotency_records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._idempotency_results: dict[tuple[str, str], AppendBatchResult] = {}
        self._outbox: list[GameplayOutboxEntry] = []
        self._outbox_by_id: dict[str, GameplayOutboxEntry] = {}

    def append_batch(self, payload: AtomicEventBatch | dict[str, Any]) -> AppendBatchResult:
        transaction_id, command_id = self._extract_identity(payload)
        if self._contains_outbox_projection_failure(payload):
            return _empty_result(
                transaction_id=transaction_id,
                command_id=command_id,
                error_code="outbox_projection_failed",
                message="outbox projection construction failed",
                failed_stage="batch_validation",
            )
        try:
            batch = payload if isinstance(payload, AtomicEventBatch) else AtomicEventBatch.model_validate(payload)
        except ValidationError as exc:
            return _empty_result(
                transaction_id=transaction_id,
                command_id=command_id,
                error_code=self._validation_error_code(exc),
                message=str(exc.errors()[0].get("msg", "batch schema invalid")),
                failed_stage="batch_validation",
            )

        idempotency_key = (
            batch.idempotency_record.principal_ref,
            batch.idempotency_record.idempotency_key,
        )
        existing_record = self._idempotency_records.get(idempotency_key)
        if existing_record is not None:
            existing_result = self._idempotency_results[idempotency_key]
            if existing_record.payload_digest == batch.idempotency_record.payload_digest:
                return existing_result.model_copy(update={"idempotency_status": "duplicate_replayed"}, deep=True)
            return _empty_result(
                transaction_id=batch.transaction_id,
                command_id=batch.command_id,
                error_code="idempotency_key_reused",
                message="idempotency key was reused with a different payload digest",
                failed_stage="idempotency",
            )

        for event in batch.events:
            if event.stream_id not in batch.expected_stream_revisions:
                return _empty_result(
                    transaction_id=batch.transaction_id,
                    command_id=batch.command_id,
                    error_code="missing_expected_revision",
                    message="batch event stream is missing expected revision",
                    failed_stage="revision_check",
                    stream_id=event.stream_id,
                )

        for stream_id, expected_revision in batch.expected_stream_revisions.items():
            actual_revision = self.get_stream_head(stream_id)
            if actual_revision != expected_revision:
                return _empty_result(
                    transaction_id=batch.transaction_id,
                    command_id=batch.command_id,
                    error_code="revision_conflict",
                    message="stream revision conflict",
                    failed_stage="revision_check",
                    expected_revision=expected_revision,
                    actual_revision=actual_revision,
                    stream_id=stream_id,
                )

        if any(event.event_id in self._events_by_id for event in batch.events):
            return _empty_result(
                transaction_id=batch.transaction_id,
                command_id=batch.command_id,
                error_code="duplicate_event_id",
                message="event_id already exists",
                failed_stage="batch_validation",
            )
        if any(entry.outbox_id in self._outbox_by_id for entry in batch.outbox_entries):
            return _empty_result(
                transaction_id=batch.transaction_id,
                command_id=batch.command_id,
                error_code="duplicate_outbox_id",
                message="outbox_id already exists",
                failed_stage="batch_validation",
            )

        stream_heads = dict(self._stream_heads)
        next_global_sequence = len(self._events) + 1
        committed_events: list[GameplayEvent] = []
        for offset, event in enumerate(batch.events):
            stream_revision = int(stream_heads.get(event.stream_id, 0)) + 1
            stream_heads[event.stream_id] = stream_revision
            committed_events.append(
                event.model_copy(
                    update={
                        "stream_revision": stream_revision,
                        "global_sequence": next_global_sequence + offset,
                    },
                    deep=True,
                )
            )

        event_sequences = {event.event_id: event.global_sequence for event in committed_events}
        committed_outbox = [
            entry.model_copy(update={"global_sequence": event_sequences[entry.event_id], "delivery_state": "pending"}, deep=True)
            for entry in batch.outbox_entries
        ]
        committed_batch = batch.model_copy(
            update={"events": committed_events, "outbox_entries": committed_outbox},
            deep=True,
        )
        result = AppendBatchResult(
            committed=True,
            transaction_id=batch.transaction_id,
            command_id=batch.command_id,
            committed_event_ids=[event.event_id for event in committed_events],
            resulting_stream_revisions={event.stream_id: event.stream_revision for event in committed_events},
            global_sequence_range=(committed_events[0].global_sequence, committed_events[-1].global_sequence),
            idempotency_status="new_commit",
            projection_refresh_hints=batch.projection_refresh_hints,
        )

        self._stream_heads = defaultdict(int, stream_heads)
        self._events.extend(committed_events)
        self._events_by_id.update({event.event_id: event for event in committed_events})
        self._transactions.append(committed_batch)
        self._transaction_results[batch.transaction_id] = result
        self._idempotency_records[idempotency_key] = batch.idempotency_record
        self._idempotency_results[idempotency_key] = result
        self._outbox.extend(committed_outbox)
        self._outbox_by_id.update({entry.outbox_id: entry for entry in committed_outbox})
        return result.model_copy(deep=True)

    def read_stream(self, stream_id: str, *, from_revision: int = 1, to_revision: int | None = None) -> list[GameplayEvent]:
        events = [event for event in self._events if event.stream_id == stream_id and event.stream_revision >= from_revision]
        if to_revision is not None:
            events = [event for event in events if event.stream_revision <= to_revision]
        return [event.model_copy(deep=True) for event in events]

    def read_events(self, *, global_sequence_from: int | None = None, global_sequence_after: int | None = None, limit: int | None = None) -> list[GameplayEvent]:
        events = self._events
        if global_sequence_from is not None:
            events = [event for event in events if event.global_sequence >= global_sequence_from]
        if global_sequence_after is not None:
            events = [event for event in events if event.global_sequence > global_sequence_after]
        events = sorted(events, key=lambda event: event.global_sequence)
        if limit is not None:
            events = events[:limit]
        return [event.model_copy(deep=True) for event in events]

    def read_transactions(self, *, global_position: int | None = None, limit: int | None = None) -> list[AtomicEventBatch]:
        transactions = self._transactions
        if global_position is not None:
            transactions = [
                batch
                for batch in transactions
                if batch.events and batch.events[-1].global_sequence >= global_position
            ]
        if limit is not None:
            transactions = transactions[:limit]
        return [batch.model_copy(deep=True) for batch in transactions]

    def get_stream_head(self, stream_id: str) -> int:
        return int(self._stream_heads.get(stream_id, 0))

    def get_event(self, event_id: str) -> GameplayEvent:
        if event_id not in self._events_by_id:
            raise KeyError(event_id)
        return self._events_by_id[event_id].model_copy(deep=True)

    def get_by_idempotency(self, principal_ref: str, idempotency_key: str) -> AppendBatchResult | None:
        result = self._idempotency_results.get((principal_ref, idempotency_key))
        return result.model_copy(deep=True) if result is not None else None

    def list_outbox(self, *, include_delivered: bool = True) -> list[GameplayOutboxEntry]:
        entries = self._outbox
        if not include_delivered:
            entries = [entry for entry in entries if entry.delivery_state in {"pending", "retryable"}]
        return [entry.model_copy(deep=True) for entry in entries]

    def mark_outbox_delivered(self, outbox_id: str) -> None:
        entry = self._outbox_by_id[outbox_id]
        self._replace_outbox(entry.model_copy(update={"delivery_state": "delivered", "last_error": None}, deep=True))

    def mark_outbox_retryable(self, outbox_id: str, error: str) -> None:
        entry = self._outbox_by_id[outbox_id]
        self._replace_outbox(
            entry.model_copy(
                update={
                    "delivery_state": "retryable",
                    "attempt_count": entry.attempt_count + 1,
                    "last_error": error,
                },
                deep=True,
            )
        )

    def _replace_outbox(self, updated: GameplayOutboxEntry) -> None:
        self._outbox_by_id[updated.outbox_id] = updated
        for index, entry in enumerate(self._outbox):
            if entry.outbox_id == updated.outbox_id:
                self._outbox[index] = updated
                break

    @staticmethod
    def _extract_identity(payload: AtomicEventBatch | dict[str, Any]) -> tuple[str, str]:
        if isinstance(payload, AtomicEventBatch):
            return payload.transaction_id, payload.command_id
        return str(payload.get("transaction_id", "") or "tx:invalid"), str(payload.get("command_id", "") or "cmd:invalid")

    @staticmethod
    def _contains_outbox_projection_failure(payload: AtomicEventBatch | dict[str, Any]) -> bool:
        entries: object
        if isinstance(payload, AtomicEventBatch):
            entries = [entry.payload_projection for entry in payload.outbox_entries]
        else:
            entries = payload.get("outbox_entries", [])
        if not isinstance(entries, list):
            return False
        for entry in entries:
            projection = entry if isinstance(entry, dict) and "payload_projection" not in entry else {}
            if isinstance(entry, dict):
                projection = entry.get("payload_projection", projection)
            if isinstance(projection, dict) and "_projection_error" in projection:
                return True
        return False

    @staticmethod
    def _validation_error_code(exc: ValidationError) -> str:
        locations = [tuple(error.get("loc", ())) for error in exc.errors()]
        if any(location and location[0] == "events" for location in locations):
            return "invalid_event_schema"
        if any(location and location[0] == "outbox_entries" for location in locations):
            return "invalid_outbox_schema"
        return "invalid_batch_schema"
