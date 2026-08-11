from __future__ import annotations

from collections import defaultdict
import json
import os
from pathlib import Path
import tempfile
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
        self._transactions: list[AtomicEventBatch] = []
        self._transaction_results: dict[str, AppendBatchResult] = {}
        self._stream_heads: dict[str, int] = defaultdict(int)
        self._idempotency_records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._idempotency_results: dict[tuple[str, str], AppendBatchResult] = {}
        self._outbox: list[GameplayOutboxEntry] = []
        self._outbox_by_id: dict[str, GameplayOutboxEntry] = {}
        self._projection_checkpoints: dict[str, ProjectionCheckpoint] = {}
        self._write_ready = True

    def append_batch(self, payload: AtomicEventBatch | dict[str, Any]) -> AppendBatchResult:
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

    def get_idempotency_record(self, principal_ref: str, idempotency_key: str) -> IdempotencyRecord | None:
        record = self._idempotency_records.get((principal_ref, idempotency_key))
        return record.model_copy(deep=True) if record is not None else None

    def list_outbox(self, *, include_delivered: bool = True) -> list[GameplayOutboxEntry]:
        entries = self._outbox
        if not include_delivered:
            entries = [entry for entry in entries if entry.delivery_state in {"pending", "retryable"}]
        return [entry.model_copy(deep=True) for entry in entries]

    def save_projection_checkpoint(self, checkpoint: ProjectionCheckpoint) -> None:
        self._projection_checkpoints[checkpoint.checkpoint_id] = checkpoint.model_copy(deep=True)

    def list_projection_checkpoints(self, *, projector_id: str | None = None) -> list[ProjectionCheckpoint]:
        checkpoints = self._projection_checkpoints.values()
        if projector_id is not None:
            checkpoints = [checkpoint for checkpoint in checkpoints if checkpoint.projector_id == projector_id]
        return sorted(
            (checkpoint.model_copy(deep=True) for checkpoint in checkpoints),
            key=lambda checkpoint: (checkpoint.last_global_sequence, checkpoint.checkpoint_id),
            reverse=True,
        )

    def set_write_readiness(self, ready: bool) -> None:
        self._write_ready = ready

    @property
    def write_ready(self) -> bool:
        return self._write_ready

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

    def export_snapshot(self) -> dict[str, Any]:
        """Return a versioned, JSON-safe durable checkpoint of authority truth."""
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
        store._transactions = transactions
        store._stream_heads = defaultdict(int, stream_heads)
        store._transaction_results = {result.transaction_id: result for result in results}
        store._outbox = outbox
        store._outbox_by_id = {entry.outbox_id: entry for entry in outbox}
        if len(store._outbox_by_id) != len(outbox) or any(entry.event_id not in store._events_by_id for entry in outbox):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_outbox_invalid")
        store._projection_checkpoints = {checkpoint.checkpoint_id: checkpoint for checkpoint in checkpoints}
        if len(store._projection_checkpoints) != len(checkpoints):
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_projection_checkpoint_invalid")
        for value in idempotency:
            if not isinstance(value, dict):
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_idempotency_invalid")
            record = IdempotencyRecord.model_validate(value.get("record"))
            result = AppendBatchResult.model_validate(value.get("result"))
            key = (str(value.get("principal_ref", "")), str(value.get("idempotency_key", "")))
            if not all(key) or key != (record.principal_ref, record.idempotency_key) or not result.committed:
                raise GameplayEventStoreSnapshotError("gameplay_snapshot_idempotency_invalid")
            store._idempotency_records[key] = record
            store._idempotency_results[key] = result
        return store

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
    """JSON-snapshot-backed store that rolls back in-memory state on write failure."""

    def __init__(
        self,
        snapshot_path: str | Path,
        *,
        event_schema_registry: EventSchemaRegistry | None = None,
    ) -> None:
        self._snapshot_path = Path(snapshot_path)
        if self._snapshot_path.exists():
            restored = GameplayEventStore.load_snapshot(
                self._snapshot_path,
                event_schema_registry=event_schema_registry,
            )
            self.__dict__.update(restored.__dict__)
        else:
            super().__init__(event_schema_registry=event_schema_registry)

    def append_batch(self, payload: AtomicEventBatch | dict[str, Any]) -> AppendBatchResult:
        before = self.export_snapshot()
        result = super().append_batch(payload)
        if not result.committed:
            return result
        try:
            self.save_snapshot(self._snapshot_path)
        except GameplayEventStoreSnapshotError:
            self.__dict__.update(GameplayEventStore.from_snapshot(before).__dict__)
            return _empty_result(
                transaction_id=result.transaction_id,
                command_id=result.command_id,
                error_code="durable_persistence_failed",
                message="authority batch was not durably persisted",
                failed_stage="durable_persistence",
                retriable=True,
            )
        return result

    def mark_outbox_delivered(self, outbox_id: str) -> None:
        self._persist_outbox_update(lambda: super(DurableGameplayEventStore, self).mark_outbox_delivered(outbox_id))

    def mark_outbox_retryable(self, outbox_id: str, error: str) -> None:
        self._persist_outbox_update(lambda: super(DurableGameplayEventStore, self).mark_outbox_retryable(outbox_id, error))

    def _persist_outbox_update(self, update: Any) -> None:
        before = self.export_snapshot()
        update()
        try:
            self.save_snapshot(self._snapshot_path)
        except GameplayEventStoreSnapshotError:
            self.__dict__.update(GameplayEventStore.from_snapshot(before).__dict__)
            raise
