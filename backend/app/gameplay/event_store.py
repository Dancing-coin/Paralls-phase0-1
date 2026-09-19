from __future__ import annotations

from bisect import bisect_left
from collections import defaultdict
from itertools import islice
import json
import os
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any

from pydantic import ValidationError

from app.gameplay.models import (
    AppendBatchResult,
    AtomicEventBatch,
    GameplayEvent,
    GameplayFailure,
    GameplayOutboxEntry,
    IdempotencyRecord,
    ProjectionCheckpoint,
)
from app.gameplay.event_schema_registry import EventSchemaRegistry, EventSchemaRegistryError


class GameplayEventStoreSnapshotError(ValueError):
    pass


def _limit(value: int) -> int:
    if value < 0:
        raise ValueError("gameplay_query_limit_invalid")
    return value


def _snapshot_list(snapshot: dict[str, Any], key: str) -> list[object]:
    value = snapshot.get(key)
    if not isinstance(value, list):
        raise GameplayEventStoreSnapshotError("gameplay_snapshot_invalid")
    return value


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

    def __init__(self, *, event_schema_registry: EventSchemaRegistry | None = None) -> None:
        self._event_schema_registry = event_schema_registry
        self._events: list[GameplayEvent] = []
        self._events_by_id: dict[str, GameplayEvent] = {}
        self._events_by_stream: dict[str, list[GameplayEvent]] = defaultdict(list)
        self._transactions: list[AtomicEventBatch] = []
        self._transaction_end_sequences: list[int] = []
        self._transaction_results: dict[str, AppendBatchResult] = {}
        self._stream_heads: dict[str, int] = defaultdict(int)
        self._idempotency_records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._idempotency_results: dict[tuple[str, str], AppendBatchResult] = {}
        self._outbox: list[GameplayOutboxEntry] = []
        self._outbox_by_id: dict[str, GameplayOutboxEntry] = {}
        self._outbox_positions: dict[str, int] = {}
        self._pending_outbox: dict[str, GameplayOutboxEntry] = {}
        self._pending_projection_refresh: set[str] = set()
        self._projection_checkpoints: dict[str, ProjectionCheckpoint] = {}
        self._write_ready = True
        self._lock = RLock()

    def append_batch(self, payload: AtomicEventBatch | dict[str, Any]) -> AppendBatchResult:
        with self._lock:
            batch = self._validate_append_payload(payload)
            if isinstance(batch, AppendBatchResult):
                return batch
            key = (batch.idempotency_record.principal_ref, batch.idempotency_record.idempotency_key)
            prepared = self._prepare_append(
                batch, existing_record=self._idempotency_records.get(key),
                existing_result=self._idempotency_results.get(key),
                stream_heads={stream: self._stream_heads.get(stream, 0) for stream in
                              batch.expected_stream_revisions.keys() | batch.read_stream_revisions.keys()},
                transaction_exists=batch.transaction_id in self._transaction_results,
                existing_event_ids={event.event_id for event in batch.events if event.event_id in self._events_by_id},
                existing_outbox_ids={entry.outbox_id for entry in batch.outbox_entries if entry.outbox_id in self._outbox_by_id},
                last_global_sequence=len(self._events),
            )
            if isinstance(prepared, AppendBatchResult):
                return prepared
            committed_batch, result = prepared
            return self._install_batch(committed_batch, result)

    def _validate_append_payload(self, payload: AtomicEventBatch | dict[str, Any]) -> AtomicEventBatch | AppendBatchResult:
        transaction_id, command_id = self._extract_identity(payload)
        if not self._write_ready:
            return _empty_result(
                transaction_id=transaction_id,
                command_id=command_id,
                error_code="projection_not_ready",
                message="authority projections are not ready for writes",
                failed_stage="projection_readiness",
                retriable=True,
            )
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
        if self._event_schema_registry is not None:
            try:
                for event in batch.events:
                    self._event_schema_registry.require(event.event_type, event.schema_version)
            except EventSchemaRegistryError:
                return _empty_result(transaction_id=batch.transaction_id, command_id=batch.command_id, error_code="event_schema_unregistered", message="event type/version is not registered", failed_stage="event_schema")

        return batch

    @staticmethod
    def _prepare_append(
        batch: AtomicEventBatch, *, existing_record: IdempotencyRecord | None,
        existing_result: AppendBatchResult | None, stream_heads: dict[str, int],
        transaction_exists: bool, existing_event_ids: set[str], existing_outbox_ids: set[str],
        last_global_sequence: int,
    ) -> tuple[AtomicEventBatch, AppendBatchResult] | AppendBatchResult:
        """两种存储共用的纯准备阶段，只接收当前批次涉及的已有值。"""
        if existing_record is not None:
            assert existing_result is not None
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

        for stream_id, expected_revision in batch.read_stream_revisions.items():
            write_revision = batch.expected_stream_revisions.get(stream_id)
            if write_revision is not None and write_revision != expected_revision:
                return _empty_result(
                    transaction_id=batch.transaction_id,
                    command_id=batch.command_id,
                    error_code="revision_conflict",
                    message="stream revision conflict",
                    failed_stage="revision_check",
                    expected_revision=expected_revision,
                    actual_revision=write_revision,
                    stream_id=stream_id,
                )

        revision_vector = dict(batch.expected_stream_revisions)
        for stream_id, expected_revision in batch.read_stream_revisions.items():
            revision_vector.setdefault(stream_id, expected_revision)

        for stream_id, expected_revision in revision_vector.items():
            actual_revision = int(stream_heads.get(stream_id, 0))
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

        if transaction_exists:
            return _empty_result(transaction_id=batch.transaction_id, command_id=batch.command_id,
                error_code="duplicate_transaction_id", message="transaction_id already exists", failed_stage="batch_validation")

        event_ids = [event.event_id for event in batch.events]
        if len(set(event_ids)) != len(event_ids) or any(
            event_id in existing_event_ids for event_id in event_ids
        ):
            return _empty_result(
                transaction_id=batch.transaction_id,
                command_id=batch.command_id,
                error_code="duplicate_event_id",
                message="event_id already exists",
                failed_stage="batch_validation",
            )
        outbox_ids = [entry.outbox_id for entry in batch.outbox_entries]
        if len(set(outbox_ids)) != len(outbox_ids) or any(
            outbox_id in existing_outbox_ids for outbox_id in outbox_ids
        ):
            return _empty_result(
                transaction_id=batch.transaction_id,
                command_id=batch.command_id,
                error_code="duplicate_outbox_id",
                message="outbox_id already exists",
                failed_stage="batch_validation",
            )

        stream_heads = dict(stream_heads)
        next_global_sequence = last_global_sequence + 1
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

        return committed_batch, result

    def _install_batch(self, batch: AtomicEventBatch, result: AppendBatchResult) -> AppendBatchResult:
        idempotency_key = (batch.idempotency_record.principal_ref, batch.idempotency_record.idempotency_key)
        self._stream_heads.update(result.resulting_stream_revisions)
        self._events.extend(batch.events)
        self._events_by_id.update({event.event_id: event for event in batch.events})
        for event in batch.events:
            self._events_by_stream[event.stream_id].append(event)
        self._transactions.append(batch)
        self._transaction_end_sequences.append(batch.events[-1].global_sequence)
        self._transaction_results[batch.transaction_id] = result
        self._idempotency_records[idempotency_key] = batch.idempotency_record
        self._idempotency_results[idempotency_key] = result
        self._outbox_positions.update({entry.outbox_id: len(self._outbox) + index for index, entry in enumerate(batch.outbox_entries)})
        self._outbox.extend(batch.outbox_entries)
        self._outbox_by_id.update({entry.outbox_id: entry for entry in batch.outbox_entries})
        self._pending_outbox.update({entry.outbox_id: entry for entry in batch.outbox_entries})
        if batch.outbox_entries or batch.projection_refresh_hints:
            self._pending_projection_refresh.add(batch.transaction_id)
        return result.model_copy(deep=True)

    def read_stream(self, stream_id: str, *, from_revision: int = 1, to_revision: int | None = None, limit: int | None = None, event_type: str | None = None) -> list[GameplayEvent]:
        with self._lock:
            events = self._events_by_stream.get(stream_id, ())
            start = max(0, from_revision - 1)
            end = max(0, to_revision) if to_revision is not None else len(events)
            if limit is not None and event_type is None:
                end = min(end, start + _limit(limit))
            events = events[start:end]
            if event_type is not None:
                events = [event for event in events if event.event_type == event_type]
            if limit is not None:
                events = events[:_limit(limit)]
            return [
                self._events_by_id.get(event.event_id, event).model_copy(deep=True)
                for event in events
            ]

    def read_events(self, *, global_sequence_from: int | None = None, global_sequence_after: int | None = None, limit: int | None = None, event_type: str | None = None) -> list[GameplayEvent]:
        with self._lock:
            start_sequence = 1
            if global_sequence_from is not None:
                start_sequence = max(start_sequence, global_sequence_from)
            if global_sequence_after is not None:
                start_sequence = max(start_sequence, global_sequence_after + 1)
            start = max(0, start_sequence - 1)
            # 直接按序号起读，不能让 islice 从零遍历游标之前的全部历史。
            events = (self._events[index] for index in range(start, len(self._events)))
            if event_type is not None:
                events = (event for event in events if event.event_type == event_type)
            if limit is not None:
                events = islice(events, _limit(limit))
            return [event.model_copy(deep=True) for event in events]

    def read_transactions(self, *, global_position: int | None = None, limit: int | None = None) -> list[AtomicEventBatch]:
        with self._lock:
            start = bisect_left(self._transaction_end_sequences, global_position) if global_position is not None else 0
            end = None if limit is None else start + _limit(limit)
            transactions = self._transactions[start:end]
            return [batch.model_copy(deep=True) for batch in transactions]

    def get_transaction(self, transaction_id: str) -> AtomicEventBatch | None:
        with self._lock:
            result = self._transaction_results.get(transaction_id)
            if result is None:
                return None
            index = bisect_left(self._transaction_end_sequences, result.global_sequence_range[1])
            return self._transactions[index].model_copy(deep=True)

    def get_stream_head(self, stream_id: str) -> int:
        with self._lock:
            return int(self._stream_heads.get(stream_id, 0))

    def get_stream_heads(self) -> dict[str, int]:
        """Return the immutable source revision vector without scanning history."""
        with self._lock:
            return dict(self._stream_heads)

    def get_last_global_sequence(self) -> int:
        with self._lock:
            return len(self._events)

    def get_projection_checkpoint(self, checkpoint_id: str) -> ProjectionCheckpoint | None:
        with self._lock:
            checkpoint = self._projection_checkpoints.get(checkpoint_id)
            return checkpoint.model_copy(deep=True) if checkpoint is not None else None

    def get_event(self, event_id: str) -> GameplayEvent:
        with self._lock:
            if event_id not in self._events_by_id:
                raise KeyError(event_id)
            return self._events_by_id[event_id].model_copy(deep=True)

    def get_by_idempotency(self, principal_ref: str, idempotency_key: str) -> AppendBatchResult | None:
        with self._lock:
            result = self._idempotency_results.get((principal_ref, idempotency_key))
            return result.model_copy(deep=True) if result is not None else None

    def get_idempotency_record(self, principal_ref: str, idempotency_key: str) -> IdempotencyRecord | None:
        with self._lock:
            record = self._idempotency_records.get((principal_ref, idempotency_key))
            return record.model_copy(deep=True) if record is not None else None

    def list_outbox(self, *, include_delivered: bool = True, topic: str | None = None,
                    transaction_id: str | None = None, after_cursor: tuple[int, str] | None = None,
                    through_sequence: int | None = None,
                    limit: int | None = None) -> list[GameplayOutboxEntry]:
        with self._lock:
            if transaction_id is not None:
                transaction = self.get_transaction(transaction_id)
                entries = (self._outbox_by_id[entry.outbox_id] for entry in transaction.outbox_entries) if transaction else ()
            else:
                entries = self._outbox if include_delivered else self._pending_outbox.values()
            matching = sorted((entry for entry in entries
                if (include_delivered or entry.delivery_state != "delivered")
                and (topic is None or entry.topic == topic)
                and (through_sequence is None or entry.global_sequence <= through_sequence)
                and (after_cursor is None or (entry.global_sequence, entry.outbox_id) > after_cursor)),
                key=lambda entry: (entry.global_sequence, entry.outbox_id))
            if limit is not None:
                matching = matching[:_limit(limit)]
            return [entry.model_copy(deep=True) for entry in matching]

    def list_pending_projection_refresh(self, *, after_sequence: int = 0,
                                        through_sequence: int | None = None,
                                        limit: int | None = None) -> list[AtomicEventBatch]:
        with self._lock:
            if limit is not None:
                _limit(limit)
            pending = sorted((self._transaction_results[tx].global_sequence_range[1], tx)
                             for tx in self._pending_projection_refresh)
            ready = []
            for sequence, transaction_id in pending:
                if sequence <= after_sequence or (through_sequence is not None and sequence > through_sequence):
                    continue
                if limit is not None and len(ready) >= limit:
                    break
                transaction = self.get_transaction(transaction_id)
                if all(self._outbox_by_id[entry.outbox_id].delivery_state == "delivered" for entry in transaction.outbox_entries):
                    ready.append(transaction)
            return ready

    def mark_projection_refreshed(self, transaction_id: str) -> bool:
        with self._lock:
            if transaction_id not in self._pending_projection_refresh:
                return False
            transaction = self.get_transaction(transaction_id)
            if any(self._outbox_by_id[entry.outbox_id].delivery_state != "delivered" for entry in transaction.outbox_entries):
                return False
            self._pending_projection_refresh.remove(transaction_id)
            return True

    def get_outbox(self, outbox_id: str) -> GameplayOutboxEntry:
        with self._lock:
            return self._outbox_by_id[outbox_id].model_copy(deep=True)

    def save_projection_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        self.save_projection_checkpoints_atomic([checkpoint])

    def save_projection_checkpoints_atomic(self, checkpoints: list[ProjectionCheckpoint]) -> None:
        with self._lock:
            copied = {checkpoint.checkpoint_id: checkpoint.model_copy(deep=True) for checkpoint in checkpoints}
            self._projection_checkpoints.update(copied)

    def list_projection_checkpoints(self, *, projector_id: str | None = None,
                                    limit: int | None = None) -> list[ProjectionCheckpoint]:
        with self._lock:
            matching = sorted((checkpoint for checkpoint in self._projection_checkpoints.values()
                if projector_id is None or checkpoint.projector_id == projector_id),
                key=lambda checkpoint: (checkpoint.last_global_sequence, checkpoint.checkpoint_id), reverse=True)
            if limit is not None:
                matching = matching[:_limit(limit)]
            return [checkpoint.model_copy(deep=True) for checkpoint in matching]

    def set_write_readiness(self, ready: bool) -> None:
        with self._lock:
            self._write_ready = ready

    @property
    def write_ready(self) -> bool:
        with self._lock:
            return self._write_ready

    def mark_outbox_delivered(self, outbox_id: str) -> None:
        with self._lock:
            entry = self._outbox_by_id[outbox_id]
            self._replace_outbox(entry.model_copy(update={"delivery_state": "delivered", "last_error": None}, deep=True))

    def mark_outbox_retryable(self, outbox_id: str, error: str) -> None:
        with self._lock:
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

    def export_snapshot(self) -> dict[str, Any]:
        """Return a versioned, JSON-safe durable checkpoint of authority truth."""
        with self._lock:
            return {
                "snapshot_schema_version": 2,
                "events": [event.model_dump(mode="json") for event in self._events],
                "transactions": [batch.model_dump(mode="json") for batch in self._transactions],
                "transaction_results": [result.model_dump(mode="json") for result in self._transaction_results.values()],
                "idempotency": [
                    {
                        "principal_ref": principal_ref,
                        "idempotency_key": key,
                        "record": record.model_dump(mode="json"),
                        "result": self._idempotency_results[(principal_ref, key)].model_dump(mode="json"),
                    }
                    for (principal_ref, key), record in sorted(self._idempotency_records.items())
                ],
                "outbox": [entry.model_dump(mode="json") for entry in self._outbox],
                "pending_projection_refresh_ids": sorted(self._pending_projection_refresh),
                "projection_checkpoints": [
                    checkpoint.model_dump(mode="json")
                    for checkpoint in self.list_projection_checkpoints()
                ],
                "event_schema_registry": (
                    self._event_schema_registry.export_snapshot() if self._event_schema_registry is not None else None
                ),
            }

    def save_snapshot(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(self.export_snapshot(), stream, sort_keys=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, target)
        except OSError as exc:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed") from exc

    @classmethod
    def load_snapshot(
        cls,
        path: str | Path,
        *,
        event_schema_registry: EventSchemaRegistry | None = None,
    ) -> "GameplayEventStore":
        try:
            with Path(path).open("r", encoding="utf-8") as stream:
                snapshot = json.load(stream)
        except (OSError, json.JSONDecodeError) as exc:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_load_failed") from exc
        return cls.from_snapshot(snapshot, event_schema_registry=event_schema_registry)

    @classmethod
    def from_snapshot(
        cls,
        snapshot: object,
        *,
        event_schema_registry: EventSchemaRegistry | None = None,
    ) -> "GameplayEventStore":
        if not isinstance(snapshot, dict) or snapshot.get("snapshot_schema_version") not in {1, 2}:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_schema_unsupported")
        try:
            events = [GameplayEvent.model_validate(value) for value in _snapshot_list(snapshot, "events")]
            transactions = [AtomicEventBatch.model_validate(value) for value in _snapshot_list(snapshot, "transactions")]
            results = [AppendBatchResult.model_validate(value) for value in _snapshot_list(snapshot, "transaction_results")]
            outbox = [GameplayOutboxEntry.model_validate(value) for value in _snapshot_list(snapshot, "outbox")]
            idempotency = _snapshot_list(snapshot, "idempotency")
            checkpoint_values = snapshot.get("projection_checkpoints", [])
            if not isinstance(checkpoint_values, list):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_projection_checkpoint_invalid")
            checkpoints = [ProjectionCheckpoint.model_validate(value) for value in checkpoint_values]
        except (ValidationError, TypeError) as exc:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_invalid") from exc
        if [event.global_sequence for event in events] != list(range(1, len(events) + 1)) or len({event.event_id for event in events}) != len(events):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_event_order_invalid")
        stream_heads: dict[str, int] = defaultdict(int)
        for event in events:
            expected = stream_heads[event.stream_id] + 1
            if event.stream_revision != expected:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_stream_revision_invalid")
            stream_heads[event.stream_id] = expected
        if {event.event_id for batch in transactions for event in batch.events} != {event.event_id for event in events}:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")

        # A snapshot is an atomic ledger image: results, idempotency records,
        # and outbox entries must all describe the same committed transactions.
        # Without these checks a tampered snapshot could restore events while
        # silently changing duplicate/replay behavior or receipt evidence.
        transaction_ids = [batch.transaction_id for batch in transactions]
        if len(set(transaction_ids)) != len(transaction_ids):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
        event_by_id = {event.event_id: event for event in events}
        snapshot_outbox_by_id = {entry.outbox_id: entry for entry in outbox}
        snapshot_outbox_by_transaction: dict[str, set[str]] = defaultdict(set)
        for entry in outbox:
            snapshot_outbox_by_transaction[entry.transaction_id].add(entry.outbox_id)
        transaction_by_id = {batch.transaction_id: batch for batch in transactions}
        transaction_sequence_keys: list[int] = []
        for batch in transactions:
            batch_sequences = [event.global_sequence for event in batch.events]
            if batch_sequences != list(range(batch_sequences[0], batch_sequences[-1] + 1)):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
            transaction_sequence_keys.append(batch_sequences[0])
        if transaction_sequence_keys != sorted(transaction_sequence_keys):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
        result_by_transaction: dict[str, AppendBatchResult] = {}
        for result in results:
            if result.transaction_id in result_by_transaction:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")
            result_by_transaction[result.transaction_id] = result
        if set(result_by_transaction) != set(transaction_by_id):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")
        for entry in outbox:
            event = event_by_id.get(entry.event_id)
            if (
                event is None
                or entry.transaction_id != event.transaction_id
                or entry.global_sequence != event.global_sequence
            ):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_outbox_invalid")
        for transaction_id, batch in transaction_by_id.items():
            ledger_events = tuple(event_by_id.get(event.event_id) for event in batch.events)
            if any(event is None for event in ledger_events) or any(
                event.model_dump(mode="json") != ledger_event.model_dump(mode="json")
                for event, ledger_event in zip(batch.events, ledger_events)
                if ledger_event is not None
            ):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
            first_stream_revisions: dict[str, int] = {}
            for event in batch.events:
                first_stream_revisions.setdefault(event.stream_id, event.stream_revision)
            if any(
                stream_id not in batch.expected_stream_revisions
                or batch.expected_stream_revisions[stream_id] != revision - 1
                for stream_id, revision in first_stream_revisions.items()
            ):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
            batch_outbox_ids = {entry.outbox_id for entry in batch.outbox_entries}
            batch_event_ids = {event.event_id for event in batch.events}
            if any(entry.event_id not in batch_event_ids for entry in batch.outbox_entries):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
            if any(
                (
                    snapshot_outbox_by_id.get(entry.outbox_id) is None
                    or snapshot_outbox_by_id[entry.outbox_id].model_dump(
                        mode="json",
                        include={"outbox_id", "transaction_id", "event_id", "topic", "audience", "payload_projection"},
                    )
                    != entry.model_dump(
                        mode="json",
                        include={"outbox_id", "transaction_id", "event_id", "topic", "audience", "payload_projection"},
                    )
                )
                for entry in batch.outbox_entries
            ) or batch_outbox_ids != snapshot_outbox_by_transaction.get(transaction_id, set()):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
            result = result_by_transaction[transaction_id]
            if not result.committed or result.failure is not None or result.command_id != batch.command_id:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")
            committed_event_ids = tuple(event.event_id for event in batch.events)
            if tuple(result.committed_event_ids) != committed_event_ids:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")
            expected_revisions: dict[str, int] = {}
            for event in batch.events:
                expected_revisions[event.stream_id] = event.stream_revision
            if result.resulting_stream_revisions != expected_revisions:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")
            if result.global_sequence_range != (
                batch.events[0].global_sequence,
                batch.events[-1].global_sequence,
            ):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")
            if result.projection_refresh_hints != batch.projection_refresh_hints:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_result_invalid")

        outbox_ids: set[str] = set()
        for entry in outbox:
            if entry.outbox_id in outbox_ids:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_outbox_invalid")
            outbox_ids.add(entry.outbox_id)
            event = event_by_id.get(entry.event_id)
            if (
                event is None
                or entry.transaction_id != event.transaction_id
                or entry.global_sequence != event.global_sequence
            ):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_outbox_invalid")

        snapshot_registry: EventSchemaRegistry | None = None
        if snapshot.get("snapshot_schema_version") == 2:
            registry_snapshot = snapshot.get("event_schema_registry")
            if registry_snapshot is not None:
                try:
                    snapshot_registry = EventSchemaRegistry.from_snapshot(registry_snapshot)
                except EventSchemaRegistryError as exc:
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_event_schema_registry_invalid") from exc
        if event_schema_registry is not None and snapshot_registry is not None:
            if event_schema_registry.export_snapshot() != snapshot_registry.export_snapshot():
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_event_schema_registry_mismatch")
        if snapshot_registry is not None:
            try:
                for event in events:
                    snapshot_registry.require(event.event_type, event.schema_version)
            except EventSchemaRegistryError as exc:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_event_schema_registry_invalid") from exc
        store = cls(event_schema_registry=snapshot_registry or event_schema_registry)
        store._events = events
        store._events_by_id = {event.event_id: event for event in events}
        store._events_by_stream = defaultdict(list)
        for event in events:
            store._events_by_stream[event.stream_id].append(event)
        store._transactions = transactions
        store._transaction_end_sequences = [batch.events[-1].global_sequence for batch in transactions]
        store._stream_heads = defaultdict(int, stream_heads)
        store._transaction_results = {result.transaction_id: result for result in results}
        store._outbox = outbox
        store._outbox_by_id = {entry.outbox_id: entry for entry in outbox}
        store._outbox_positions = {entry.outbox_id: index for index, entry in enumerate(outbox)}
        store._pending_outbox = {entry.outbox_id: entry for entry in outbox if entry.delivery_state != "delivered"}
        if len(store._outbox_by_id) != len(outbox) or any(entry.event_id not in store._events_by_id for entry in outbox):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_outbox_invalid")
        eligible_refresh = {batch.transaction_id for batch in transactions if batch.outbox_entries or batch.projection_refresh_hints}
        pending_refresh = snapshot.get("pending_projection_refresh_ids", sorted(eligible_refresh))
        if not isinstance(pending_refresh, list) or any(not isinstance(tx, str) for tx in pending_refresh):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_projection_refresh_invalid")
        pending_refresh_ids = set(pending_refresh)
        if (len(pending_refresh_ids) != len(pending_refresh) or not pending_refresh_ids <= eligible_refresh
                or any(entry.delivery_state != "delivered" and entry.transaction_id not in pending_refresh_ids for entry in outbox)):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_projection_refresh_invalid")
        store._pending_projection_refresh = pending_refresh_ids
        store._projection_checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}
        if len(store._projection_checkpoints) != len(checkpoints):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_projection_checkpoint_invalid")
        idempotency_transaction_ids: set[str] = set()
        idempotency_keys: set[tuple[str, str]] = set()
        for value in idempotency:
            if not isinstance(value, dict):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_idempotency_invalid")
            record = IdempotencyRecord.model_validate(value.get("record"))
            result = AppendBatchResult.model_validate(value.get("result"))
            key = (str(value.get("principal_ref", "")), str(value.get("idempotency_key", "")))
            if (
                not all(key)
                or key in idempotency_keys
                or key != (record.principal_ref, record.idempotency_key)
                or not result.committed
                or result.transaction_id not in transaction_by_id
                or transaction_by_id[result.transaction_id].idempotency_record != record
                or result.model_dump(mode="json") != result_by_transaction[result.transaction_id].model_dump(mode="json")
            ):
                if result.transaction_id in transaction_by_id and transaction_by_id[result.transaction_id].idempotency_record != record:
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_transaction_invalid")
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_idempotency_invalid")
            idempotency_keys.add(key)
            idempotency_transaction_ids.add(result.transaction_id)
            store._idempotency_records[key] = record
            store._idempotency_results[key] = result
        if idempotency_transaction_ids != set(transaction_by_id):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_idempotency_invalid")
        return store

    def _replace_outbox(self, updated: GameplayOutboxEntry) -> None:
        self._outbox_by_id[updated.outbox_id] = updated
        self._outbox[self._outbox_positions[updated.outbox_id]] = updated
        if updated.delivery_state == "delivered":
            self._pending_outbox.pop(updated.outbox_id, None)
        else:
            self._pending_outbox[updated.outbox_id] = updated

    @staticmethod
    def _extract_identity(payload: AtomicEventBatch | dict[str, Any]) -> tuple[str, str]:
        if isinstance(payload, AtomicEventBatch):
            return payload.transaction_id, payload.command_id
        return str(payload.get("transaction_id", "") or "tx:invalid"), str(payload.get("command_id", "") or "cmd:invalid")

    @staticmethod
    def _contains_outbox_projection_failure(payload: AtomicEventBatch | dict[str, Any]) -> bool:
        entries = [entry.payload_projection for entry in payload.outbox_entries] if isinstance(payload, AtomicEventBatch) else payload.get("outbox_entries", [])
        if not isinstance(entries, list):
            return False
        return any(isinstance((entry.get("payload_projection", entry) if isinstance(entry, dict) else entry), dict) and "_projection_error" in (entry.get("payload_projection", entry) if isinstance(entry, dict) else entry) for entry in entries)

    @staticmethod
    def _validation_error_code(exc: ValidationError) -> str:
        locations = [tuple(error.get("loc", ())) for error in exc.errors()]
        if any(location and location[0] == "events" for location in locations):
            return "invalid_event_schema"
        if any(location and location[0] == "outbox_entries" for location in locations):
            return "invalid_outbox_schema"
        return "invalid_batch_schema"


class DurableGameplayEventStore(GameplayEventStore):
    """SQLite 是持久账本；正常启动和定向查询不创建全历史内存副本。"""

    _QUERY_INDEXES = (
        "CREATE INDEX IF NOT EXISTS outbox_topic_sequence ON outbox(topic, global_sequence, id)",
        "CREATE INDEX IF NOT EXISTS checkpoints_sequence ON checkpoints(global_sequence DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS events_stream_type_revision ON events(stream_id, json_extract(value,'$.event_type'), stream_revision)",
        "CREATE INDEX IF NOT EXISTS events_type_sequence ON events(json_extract(value,'$.event_type'), global_sequence)",
    )
    _SCHEMA = (
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS transactions (sequence INTEGER PRIMARY KEY, batch TEXT NOT NULL, result TEXT NOT NULL, transaction_id TEXT NOT NULL UNIQUE, principal_ref TEXT NOT NULL, idempotency_key TEXT NOT NULL, payload_digest TEXT NOT NULL, refresh_state TEXT)",
        "CREATE TABLE IF NOT EXISTS events (global_sequence INTEGER PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, stream_id TEXT NOT NULL, stream_revision INTEGER NOT NULL, transaction_id TEXT NOT NULL, value TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS stream_heads (stream_id TEXT PRIMARY KEY, revision INTEGER NOT NULL)",
        "CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, value TEXT NOT NULL, delivery_state TEXT NOT NULL, topic TEXT NOT NULL, global_sequence INTEGER NOT NULL, transaction_id TEXT NOT NULL, event_id TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS checkpoints (id TEXT PRIMARY KEY, value TEXT NOT NULL, projector_id TEXT NOT NULL, global_sequence INTEGER NOT NULL)",
        "CREATE UNIQUE INDEX IF NOT EXISTS transactions_identity ON transactions(transaction_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS transactions_idempotency ON transactions(principal_ref, idempotency_key)",
        "CREATE UNIQUE INDEX IF NOT EXISTS events_stream_revision ON events(stream_id, stream_revision)",
        "CREATE INDEX IF NOT EXISTS events_transaction_sequence ON events(transaction_id, global_sequence)",
        "CREATE INDEX IF NOT EXISTS outbox_sequence ON outbox(global_sequence, id)",
        "CREATE INDEX IF NOT EXISTS outbox_transaction_sequence ON outbox(transaction_id, global_sequence, id)",
        "CREATE INDEX IF NOT EXISTS outbox_event ON outbox(event_id)",
        "CREATE INDEX IF NOT EXISTS outbox_pending_sequence ON outbox(global_sequence, id) WHERE delivery_state <> 'delivered'",
        "CREATE INDEX IF NOT EXISTS outbox_pending_topic_sequence ON outbox(topic, global_sequence, id) WHERE delivery_state <> 'delivered'",
        "CREATE INDEX IF NOT EXISTS checkpoints_projector_sequence ON checkpoints(projector_id, global_sequence DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS transactions_pending_refresh ON transactions(sequence) WHERE refresh_state='pending'",
    ) + _QUERY_INDEXES

    def __init__(self, snapshot_path: str | Path, *, event_schema_registry: EventSchemaRegistry | None = None) -> None:
        self._snapshot_path = Path(snapshot_path)
        self._snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(event_schema_registry=event_schema_registry)
        self._connection: sqlite3.Connection | None = None
        self._closed = False
        restored = None
        if self._snapshot_path.exists():
            with self._snapshot_path.open("rb") as stream:
                is_database = stream.read(16) == b"SQLite format 3\x00"
            if is_database:
                self._load_database(event_schema_registry)
                return
            restored = GameplayEventStore.load_snapshot(self._snapshot_path, event_schema_registry=event_schema_registry)
            self._event_schema_registry = restored._event_schema_registry
        # 迁移是显式的一次全量工作；替换前失败不改原 JSON。
        handle, temporary = tempfile.mkstemp(prefix=".gameplay-", suffix=".db", dir=self._snapshot_path.parent)
        os.close(handle)
        try:
            with closing(sqlite3.connect(temporary)) as connection, connection:
                for statement in self._SCHEMA:
                    connection.execute(statement)
                registry = self._event_schema_registry.export_snapshot() if self._event_schema_registry else None
                connection.executemany("INSERT INTO metadata VALUES (?, ?)",
                    [("schema", "2"), ("registry", json.dumps(registry, sort_keys=True)), ("last_global_sequence", "0")])
                if restored is not None:
                    for batch in restored._transactions:
                        self._write_delta(connection=connection, batch=batch, result=restored._transaction_results[batch.transaction_id])
                    for entry in restored._outbox:
                        self._write_delta(connection=connection, outbox=entry)
                    for batch in restored._transactions:
                        if (batch.outbox_entries or batch.projection_refresh_hints) and batch.transaction_id not in restored._pending_projection_refresh:
                            connection.execute("UPDATE transactions SET refresh_state='done' WHERE transaction_id=?", (batch.transaction_id,))
                    self._write_delta(connection=connection, checkpoints=list(restored._projection_checkpoints.values()))
            os.replace(temporary, self._snapshot_path)
        except (OSError, sqlite3.Error) as exc:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed") from exc
        finally:
            if Path(temporary).exists():
                os.unlink(temporary)

    def _database_connection(self) -> sqlite3.Connection:
        # 调用者持有原 store 锁；读语句完成即释放快照，事务仍逐批提交。
        if self._closed:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_closed")
        if self._connection is None:
            connection = sqlite3.connect(self._snapshot_path, check_same_thread=False)
            try:
                if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_wal_unavailable")
                connection.execute("PRAGMA synchronous=FULL")
            except BaseException:
                connection.close()
                raise
            self._connection = connection
        return self._connection

    def _discard_connection(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._discard_connection()

    def _snapshot_connection(self) -> sqlite3.Connection:
        if self._closed:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_closed")
        return sqlite3.connect(self._snapshot_path)

    @contextmanager
    def _transaction(self, connection: sqlite3.Connection | None = None):
        if connection is not None:
            yield connection
            return
        with self._lock:
            if self._closed:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_closed")
            try:
                with self._database_connection() as owned:
                    owned.execute("BEGIN IMMEDIATE")
                    yield owned
            except BaseException:
                # 原事务退出已回滚；失败连接不带入下一次重试。
                self._discard_connection()
                raise

    def _load_database(self, registry: EventSchemaRegistry | None) -> None:
        try:
            with closing(sqlite3.connect(self._snapshot_path)) as connection:
                metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                if metadata.get("schema") == "1":
                    self._migrate_schema_one(connection, registry)
                    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
                if metadata.get("schema") != "2":
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_schema_unsupported")
                if int(metadata["last_global_sequence"]) < 0:
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_sequence_invalid")
                saved_registry = json.loads(metadata["registry"])
                loaded = EventSchemaRegistry.from_snapshot(saved_registry) if saved_registry is not None else None
                if loaded is not None and registry is not None and loaded.export_snapshot() != registry.export_snapshot():
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_event_schema_registry_mismatch")
                self._event_schema_registry = loaded or registry
                # 旧 schema2 首次补索引；已有索引时 SQLite 不重扫历史，DDL 原子提交。
                with connection:
                    connection.execute("BEGIN IMMEDIATE")
                    for statement in self._QUERY_INDEXES:
                        connection.execute(statement)
        except (OSError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, GameplayEventStoreSnapshotError):
                raise
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_load_failed") from exc

    def _migrate_schema_one(self, connection: sqlite3.Connection, registry: EventSchemaRegistry | None) -> None:
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
            if metadata.get("schema") == "2":
                return
            snapshot = self._snapshot_from_connection(connection, legacy=True)
            restored = GameplayEventStore.from_snapshot(snapshot, event_schema_registry=registry)
            self._event_schema_registry = restored._event_schema_registry
            additions = {
                "transactions": ("transaction_id TEXT", "principal_ref TEXT", "idempotency_key TEXT", "payload_digest TEXT", "refresh_state TEXT"),
                "outbox": ("delivery_state TEXT", "topic TEXT", "global_sequence INTEGER", "transaction_id TEXT", "event_id TEXT"),
                "checkpoints": ("projector_id TEXT", "global_sequence INTEGER"),
            }
            for table, columns in additions.items():
                for column in columns:
                    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column}")
            for statement in self._SCHEMA:
                connection.execute(statement)
            for batch in restored._transactions:
                key = batch.idempotency_record
                connection.execute("UPDATE transactions SET transaction_id=?, principal_ref=?, idempotency_key=?, payload_digest=?, refresh_state=? WHERE sequence=?",
                    (batch.transaction_id, key.principal_ref, key.idempotency_key, key.payload_digest,
                     "pending" if batch.outbox_entries or batch.projection_refresh_hints else None, batch.events[-1].global_sequence))
                self._index_events(connection, batch)
            for entry in restored._outbox:
                self._write_delta(connection=connection, outbox=entry)
            self._write_delta(connection=connection, checkpoints=list(restored._projection_checkpoints.values()))
            connection.execute("INSERT INTO metadata VALUES ('last_global_sequence', ?)", (str(restored.get_last_global_sequence()),))
            connection.execute("UPDATE metadata SET value='2' WHERE key='schema'")

    @staticmethod
    def _index_events(connection: sqlite3.Connection, batch: AtomicEventBatch) -> None:
        connection.executemany("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            ((event.global_sequence, event.event_id, event.stream_id, event.stream_revision, event.transaction_id, event.model_dump_json()) for event in batch.events))
        heads = {event.stream_id: event.stream_revision for event in batch.events}
        connection.executemany("INSERT INTO stream_heads VALUES (?, ?) ON CONFLICT(stream_id) DO UPDATE SET revision=excluded.revision", heads.items())

    @staticmethod
    def _matching_rows(connection: sqlite3.Connection, table: str, column: str, values: list[str], selected: str) -> list[tuple]:
        # SQL 标识符全部来自本模块常量；每页避开较旧 SQLite 的变量数量上限。
        rows = []
        for start in range(0, len(values), 800):
            page = values[start:start + 800]
            rows.extend(connection.execute(f"SELECT {selected} FROM {table} WHERE {column} IN ({','.join('?' for _ in page)})", page))
        return rows

    def append_batch(self, payload: AtomicEventBatch | dict[str, Any]) -> AppendBatchResult:
        with self._lock:
            batch = self._validate_append_payload(payload)
            if isinstance(batch, AppendBatchResult):
                return batch
            try:
                with self._transaction() as connection:
                    key = batch.idempotency_record
                    previous = connection.execute("SELECT payload_digest, result FROM transactions WHERE principal_ref=? AND idempotency_key=?",
                        (key.principal_ref, key.idempotency_key)).fetchone()
                    streams = list(batch.expected_stream_revisions.keys() | batch.read_stream_revisions.keys())
                    prepared = self._prepare_append(batch,
                        existing_record=IdempotencyRecord(principal_ref=key.principal_ref, idempotency_key=key.idempotency_key, payload_digest=previous[0]) if previous else None,
                        existing_result=AppendBatchResult.model_validate_json(previous[1]) if previous else None,
                        stream_heads=dict(self._matching_rows(connection, "stream_heads", "stream_id", streams, "stream_id, revision")),
                        transaction_exists=connection.execute("SELECT 1 FROM transactions WHERE transaction_id=?", (batch.transaction_id,)).fetchone() is not None,
                        existing_event_ids={row[0] for row in self._matching_rows(connection, "events", "event_id", [event.event_id for event in batch.events], "event_id")},
                        existing_outbox_ids={row[0] for row in self._matching_rows(connection, "outbox", "id", [entry.outbox_id for entry in batch.outbox_entries], "id")},
                        last_global_sequence=int(connection.execute("SELECT value FROM metadata WHERE key='last_global_sequence'").fetchone()[0]),
                    )
                    if isinstance(prepared, AppendBatchResult):
                        return prepared
                    committed_batch, result = prepared
                    self._write_delta(connection=connection, batch=committed_batch, result=result)
                return result.model_copy(deep=True)
            except (OSError, sqlite3.Error, GameplayEventStoreSnapshotError):
                return _empty_result(transaction_id=batch.transaction_id, command_id=batch.command_id,
                    error_code="durable_persistence_failed", message="authority batch was not durably persisted",
                    failed_stage="durable_persistence", retriable=True)

    def _write_delta(self, *, batch: AtomicEventBatch | None = None, result: AppendBatchResult | None = None,
                     outbox: GameplayOutboxEntry | None = None, checkpoint: ProjectionCheckpoint | None = None,
                     checkpoints: tuple[ProjectionCheckpoint, ...] | list[ProjectionCheckpoint] = (), connection: sqlite3.Connection | None = None) -> None:
        try:
            with self._transaction(connection) as target:
                if batch is not None and result is not None:
                    if self._event_schema_registry is not None:
                        registry_json = json.dumps(self._event_schema_registry.export_snapshot(), sort_keys=True)
                        target.execute("UPDATE metadata SET value=? WHERE key='registry' AND value<>?", (registry_json, registry_json))
                    key = batch.idempotency_record
                    target.execute("INSERT INTO transactions (sequence,batch,result,transaction_id,principal_ref,idempotency_key,payload_digest,refresh_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (batch.events[-1].global_sequence, batch.model_dump_json(), result.model_dump_json(), batch.transaction_id,
                         key.principal_ref, key.idempotency_key, key.payload_digest, "pending" if batch.outbox_entries or batch.projection_refresh_hints else None))
                    self._index_events(target, batch)
                    target.executemany("INSERT INTO outbox (id,value,delivery_state,topic,global_sequence,transaction_id,event_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        ((entry.outbox_id, entry.model_dump_json(), entry.delivery_state, entry.topic, entry.global_sequence, entry.transaction_id, entry.event_id) for entry in batch.outbox_entries))
                    target.execute("UPDATE metadata SET value=? WHERE key='last_global_sequence'", (str(batch.events[-1].global_sequence),))
                if outbox is not None:
                    target.execute("UPDATE outbox SET value=?, delivery_state=?, topic=?, global_sequence=?, transaction_id=?, event_id=? WHERE id=?",
                        (outbox.model_dump_json(), outbox.delivery_state, outbox.topic, outbox.global_sequence, outbox.transaction_id, outbox.event_id, outbox.outbox_id))
                for item in ([checkpoint] if checkpoint is not None else checkpoints):
                    target.execute("INSERT INTO checkpoints (id,value,projector_id,global_sequence) VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET value=excluded.value, projector_id=excluded.projector_id, global_sequence=excluded.global_sequence",
                        (item.checkpoint_id, item.model_dump_json(), item.projector_id, item.last_global_sequence))
        except (OSError, sqlite3.Error) as exc:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed") from exc

    def _rows(self, sql: str, parameters: tuple = ()) -> list[tuple]:
        with self._lock:
            try:
                return list(self._database_connection().execute(sql, parameters))
            except (OSError, sqlite3.Error) as exc:
                self._discard_connection()
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_read_failed") from exc

    def _models(self, model, sql: str, parameters: tuple = (), *, limit: int | None = None) -> list:
        if limit is not None:
            sql += " LIMIT ?"
            parameters += (_limit(limit),)
        try:
            return [model.model_validate_json(row[0]) for row in self._rows(sql, parameters)]
        except (ValueError, TypeError) as exc:
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_row_invalid") from exc

    def read_stream(self, stream_id: str, *, from_revision: int = 1, to_revision: int | None = None, limit: int | None = None, event_type: str | None = None) -> list[GameplayEvent]:
        sql = "SELECT value FROM events WHERE stream_id=? AND stream_revision>=?"
        parameters = (stream_id, max(1, from_revision))
        if to_revision is not None:
            sql += " AND stream_revision<=?"
            parameters += (to_revision,)
        if event_type is not None:
            sql += " AND json_extract(value,'$.event_type')=?"
            parameters += (event_type,)
        return self._models(GameplayEvent, sql + " ORDER BY stream_revision", parameters, limit=limit)

    def read_events(self, *, global_sequence_from: int | None = None, global_sequence_after: int | None = None, limit: int | None = None, event_type: str | None = None) -> list[GameplayEvent]:
        start = max(1, global_sequence_from or 1, (global_sequence_after or 0) + 1)
        sql, parameters = "SELECT value FROM events WHERE global_sequence>=?", (start,)
        if event_type is not None:
            sql += " AND json_extract(value,'$.event_type')=?"
            parameters += (event_type,)
        return self._models(GameplayEvent, sql + " ORDER BY global_sequence", parameters, limit=limit)

    def read_transactions(self, *, global_position: int | None = None, limit: int | None = None) -> list[AtomicEventBatch]:
        return self._models(AtomicEventBatch, "SELECT batch FROM transactions WHERE sequence>=? ORDER BY sequence", (global_position or 0,), limit=limit)

    def get_transaction(self, transaction_id: str) -> AtomicEventBatch | None:
        values = self._models(AtomicEventBatch, "SELECT batch FROM transactions WHERE transaction_id=?", (transaction_id,))
        return values[0] if values else None

    def get_stream_head(self, stream_id: str) -> int:
        rows = self._rows("SELECT revision FROM stream_heads WHERE stream_id=?", (stream_id,))
        return int(rows[0][0]) if rows else 0

    def get_stream_heads(self) -> dict[str, int]:
        return dict(self._rows("SELECT stream_id, revision FROM stream_heads"))

    def get_last_global_sequence(self) -> int:
        return int(self._rows("SELECT value FROM metadata WHERE key='last_global_sequence'")[0][0])

    def get_event(self, event_id: str) -> GameplayEvent:
        values = self._models(GameplayEvent, "SELECT value FROM events WHERE event_id=?", (event_id,))
        if not values:
            raise KeyError(event_id)
        return values[0]

    def get_by_idempotency(self, principal_ref: str, idempotency_key: str) -> AppendBatchResult | None:
        values = self._models(AppendBatchResult, "SELECT result FROM transactions WHERE principal_ref=? AND idempotency_key=?", (principal_ref, idempotency_key))
        return values[0] if values else None

    def get_idempotency_record(self, principal_ref: str, idempotency_key: str) -> IdempotencyRecord | None:
        rows = self._rows("SELECT payload_digest FROM transactions WHERE principal_ref=? AND idempotency_key=?", (principal_ref, idempotency_key))
        return IdempotencyRecord(principal_ref=principal_ref, idempotency_key=idempotency_key, payload_digest=rows[0][0]) if rows else None

    def list_outbox(self, *, include_delivered: bool = True, topic: str | None = None,
                    transaction_id: str | None = None, after_cursor: tuple[int, str] | None = None,
                    through_sequence: int | None = None,
                    limit: int | None = None) -> list[GameplayOutboxEntry]:
        conditions, parameters = [], ()
        if not include_delivered:
            conditions.append("delivery_state <> 'delivered'")
        for name, value in (("topic", topic), ("transaction_id", transaction_id)):
            if value is not None:
                conditions.append(f"{name}=?")
                parameters += (value,)
        if after_cursor is not None:
            conditions.append("(global_sequence, id) > (?, ?)")
            parameters += after_cursor
        if through_sequence is not None:
            conditions.append("global_sequence<=?")
            parameters += (through_sequence,)
        sql = "SELECT value FROM outbox" + (" WHERE " + " AND ".join(conditions) if conditions else "")
        return self._models(GameplayOutboxEntry, sql + " ORDER BY global_sequence, id", parameters, limit=limit)

    def list_pending_projection_refresh(self, *, after_sequence: int = 0,
                                        through_sequence: int | None = None,
                                        limit: int | None = None) -> list[AtomicEventBatch]:
        sql = "SELECT batch FROM transactions WHERE refresh_state='pending' AND sequence>?"
        parameters = (after_sequence,)
        if through_sequence is not None:
            sql += " AND sequence<=?"
            parameters += (through_sequence,)
        sql += (" AND NOT EXISTS (SELECT 1 FROM outbox WHERE outbox.transaction_id=transactions.transaction_id"
                " AND delivery_state <> 'delivered') ORDER BY sequence")
        return self._models(AtomicEventBatch, sql, parameters, limit=limit)

    def mark_projection_refreshed(self, transaction_id: str) -> bool:
        with self._lock:
            try:
                with self._transaction() as connection:
                    updated = connection.execute(
                        "UPDATE transactions SET refresh_state='done' WHERE transaction_id=? AND refresh_state='pending'"
                        " AND NOT EXISTS (SELECT 1 FROM outbox WHERE outbox.transaction_id=transactions.transaction_id"
                        " AND delivery_state <> 'delivered')", (transaction_id,))
                    return updated.rowcount == 1
            except (OSError, sqlite3.Error) as exc:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed") from exc

    def get_outbox(self, outbox_id: str) -> GameplayOutboxEntry:
        values = self._models(GameplayOutboxEntry, "SELECT value FROM outbox WHERE id=?", (outbox_id,))
        if not values:
            raise KeyError(outbox_id)
        return values[0]

    def get_projection_checkpoint(self, checkpoint_id: str) -> ProjectionCheckpoint | None:
        values = self._models(ProjectionCheckpoint, "SELECT value FROM checkpoints WHERE id=?", (checkpoint_id,))
        return values[0] if values else None

    def list_projection_checkpoints(self, *, projector_id: str | None = None, limit: int | None = None) -> list[ProjectionCheckpoint]:
        sql = "SELECT value FROM checkpoints"
        parameters = ()
        if projector_id is not None:
            sql += " WHERE projector_id=?"
            parameters = (projector_id,)
        return self._models(ProjectionCheckpoint, sql + " ORDER BY global_sequence DESC, id DESC", parameters, limit=limit)

    def save_projection_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        with self._lock:
            self._write_delta(checkpoint=checkpoint)

    def save_projection_checkpoints_atomic(self, checkpoints: list[ProjectionCheckpoint]) -> None:
        with self._lock:
            self._write_delta(checkpoints=checkpoints)

    def mark_outbox_delivered(self, outbox_id: str) -> None:
        self._update_outbox(outbox_id, delivered=True)

    def mark_outbox_retryable(self, outbox_id: str, error: str) -> None:
        self._update_outbox(outbox_id, delivered=False, error=error)

    def _update_outbox(self, outbox_id: str, *, delivered: bool, error: str | None = None) -> None:
        with self._lock:
            try:
                with self._transaction() as connection:
                    row = connection.execute("SELECT value FROM outbox WHERE id=?", (outbox_id,)).fetchone()
                    if row is None:
                        raise KeyError(outbox_id)
                    entry = GameplayOutboxEntry.model_validate_json(row[0])
                    changes = {"delivery_state": "delivered", "last_error": None} if delivered else {
                        "delivery_state": "retryable", "attempt_count": entry.attempt_count + 1, "last_error": error}
                    self._write_delta(connection=connection, outbox=entry.model_copy(update=changes, deep=True))
            except (OSError, sqlite3.Error) as exc:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed") from exc

    @staticmethod
    def _snapshot_from_connection(connection: sqlite3.Connection, *, legacy: bool = False) -> dict[str, Any]:
        rows = list(connection.execute("SELECT batch, result FROM transactions ORDER BY sequence"))
        batches = [json.loads(row[0]) for row in rows]
        results = [json.loads(row[1]) for row in rows]
        registry = connection.execute("SELECT value FROM metadata WHERE key='registry'").fetchone()
        snapshot = {
            "snapshot_schema_version": 2,
            "events": ([event for batch in batches for event in batch["events"]] if legacy else
                       [json.loads(row[0]) for row in connection.execute("SELECT value FROM events ORDER BY global_sequence")]),
            "transactions": batches, "transaction_results": results,
            "idempotency": sorted(({"principal_ref": batch["idempotency_record"]["principal_ref"], "idempotency_key": batch["idempotency_record"]["idempotency_key"], "record": batch["idempotency_record"], "result": result}
                            for batch, result in zip(batches, results)), key=lambda value: (value["principal_ref"], value["idempotency_key"])),
            "outbox": [json.loads(row[0]) for row in connection.execute("SELECT value FROM outbox ORDER BY rowid")],
            "projection_checkpoints": sorted((json.loads(row[0]) for row in connection.execute("SELECT value FROM checkpoints")),
                                            key=lambda value: (value["last_global_sequence"], value["checkpoint_id"]), reverse=True),
            "event_schema_registry": json.loads(registry[0]),
        }
        if not legacy:
            snapshot["pending_projection_refresh_ids"] = sorted(row[0] for row in connection.execute(
                "SELECT transaction_id FROM transactions WHERE refresh_state='pending'"))
        return snapshot

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock, closing(self._snapshot_connection()) as connection, connection:
            connection.execute("BEGIN")
            return self._snapshot_from_connection(connection)

    def save_snapshot(self, path: str | Path) -> None:
        if Path(path).resolve() == self._snapshot_path.resolve():
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_export_overwrites_database")
        super().save_snapshot(path)

    def audit(self) -> None:
        """离线完整审计：验证原事实、事务结果和全部派生查询列，成本为 O(H)。"""
        with self._lock, closing(self._snapshot_connection()) as connection, connection:
            connection.execute("BEGIN")
            try:
                restored = GameplayEventStore.from_snapshot(self._snapshot_from_connection(connection), event_schema_registry=self._event_schema_registry)
                if dict(connection.execute("SELECT stream_id, revision FROM stream_heads")) != restored.get_stream_heads():
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_index_invalid")
                if int(connection.execute("SELECT value FROM metadata WHERE key='last_global_sequence'").fetchone()[0]) != restored.get_last_global_sequence():
                    raise GameplayEventStoreSnapshotError("gameplay_snapshot_index_invalid")
                for sequence, event_id, stream_id, revision, tx, value in connection.execute("SELECT global_sequence,event_id,stream_id,stream_revision,transaction_id,value FROM events"):
                    event = GameplayEvent.model_validate_json(value)
                    if (sequence, event_id, stream_id, revision, tx) != (event.global_sequence, event.event_id, event.stream_id, event.stream_revision, event.transaction_id):
                        raise GameplayEventStoreSnapshotError("gameplay_snapshot_index_invalid")
                for identity, state, topic, sequence, tx, event, value in connection.execute("SELECT id,delivery_state,topic,global_sequence,transaction_id,event_id,value FROM outbox"):
                    entry = GameplayOutboxEntry.model_validate_json(value)
                    if (identity, state, topic, sequence, tx, event) != (entry.outbox_id, entry.delivery_state, entry.topic, entry.global_sequence, entry.transaction_id, entry.event_id):
                        raise GameplayEventStoreSnapshotError("gameplay_snapshot_index_invalid")
                for identity, projector, sequence, value in connection.execute("SELECT id,projector_id,global_sequence,value FROM checkpoints"):
                    checkpoint = ProjectionCheckpoint.model_validate_json(value)
                    if (identity, projector, sequence) != (checkpoint.checkpoint_id, checkpoint.projector_id, checkpoint.last_global_sequence):
                        raise GameplayEventStoreSnapshotError("gameplay_snapshot_index_invalid")
                for sequence, tx, principal, key, digest, refresh, value in connection.execute("SELECT sequence,transaction_id,principal_ref,idempotency_key,payload_digest,refresh_state,batch FROM transactions"):
                    batch = AtomicEventBatch.model_validate_json(value)
                    record = batch.idempotency_record
                    expected_refresh = ("pending" if tx in restored._pending_projection_refresh else "done") if batch.outbox_entries or batch.projection_refresh_hints else None
                    if (sequence, tx, principal, key, digest) != (batch.events[-1].global_sequence, batch.transaction_id, record.principal_ref, record.idempotency_key, record.payload_digest) or refresh != expected_refresh:
                        raise GameplayEventStoreSnapshotError("gameplay_snapshot_index_invalid")
            except (OSError, sqlite3.Error, KeyError, ValueError, TypeError) as exc:
                if isinstance(exc, GameplayEventStoreSnapshotError):
                    raise
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_audit_failed") from exc
