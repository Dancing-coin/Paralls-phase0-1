from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from threading import RLock

from app.models.harness_execution import (
    ExecutionEnvelope,
    ExecutionPhase,
    FailureKind,
    TaskTraceRecord,
    classify_failure,
)


_TRANSITIONS: dict[ExecutionPhase, frozenset[ExecutionPhase]] = {
    "created": frozenset({"running", "aborted"}),
    "running": frozenset({"waiting", "recovering", "committed", "failed", "aborted"}),
    "waiting": frozenset({"running", "committed", "aborted"}),
    "recovering": frozenset({"running", "failed", "aborted"}),
    "failed": frozenset({"recovering", "aborted"}),
    "committed": frozenset(),
    "aborted": frozenset(),
}


class HarnessTaskLedger:
    """SQLite-backed task metadata ledger; domain facts remain in their owners."""

    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(str(self._path), check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def create(self, envelope: ExecutionEnvelope) -> ExecutionEnvelope:
        with self._lock:
            existing = self._read_row(envelope.task_id)
            if existing is not None:
                current = existing[0]
                if (
                    current.run_id != envelope.run_id
                    or current.correlation_id != envelope.correlation_id
                ):
                    raise ValueError("task_identity_conflict")
                return current
            stored = envelope.model_copy(update={"revision": 0}, deep=True)
            trace = TaskTraceRecord(
                sequence=1,
                task_id=stored.task_id,
                run_id=stored.run_id,
                correlation_id=stored.correlation_id,
                causation_id=stored.causation_id,
                stage="lifecycle",
                status="created",
                producer_ts=0,
            )
            with self._transaction():
                self._connection.execute(
                    "INSERT INTO harness_tasks(task_id, run_id, correlation_id, revision, envelope_json) VALUES (?, ?, ?, ?, ?)",
                    (stored.task_id, stored.run_id, stored.correlation_id, stored.revision, self._dump(stored)),
                )
                self._insert_trace(trace)
            return stored.model_copy(deep=True)

    def read(self, task_id: str) -> ExecutionEnvelope:
        with self._lock:
            row = self._read_row(task_id)
            if row is None:
                raise ValueError(f"unknown task: {task_id}")
            return row[0].model_copy(deep=True)

    def transition(
        self,
        task_id: str,
        *,
        expected_revision: int,
        phase: ExecutionPhase,
        producer_ts: int,
        failure_kind: FailureKind | None = None,
        checkpoint_ref: str = "",
        metadata: dict[str, object] | None = None,
    ) -> ExecutionEnvelope:
        with self._lock:
            current, _ = self._require_row(task_id)
            self._assert_revision(current, expected_revision)
            if phase not in _TRANSITIONS[current.phase]:
                if not _TRANSITIONS[current.phase]:
                    raise ValueError("terminal_task_mutation")
                raise ValueError(f"invalid transition: {current.phase} -> {phase}")
            if phase in {"running", "recovering"} and current.attempt >= current.max_attempts:
                raise ValueError("attempt budget exhausted")
            failure = classify_failure(failure_kind) if failure_kind is not None else None
            stored = current.model_copy(
                update={
                    "phase": phase,
                    "attempt": current.attempt + (1 if phase in {"running", "recovering"} else 0),
                    "checkpoint_ref": checkpoint_ref or current.checkpoint_ref,
                    "failure": failure,
                    "revision": current.revision + 1,
                },
                deep=True,
            )
            trace_metadata = dict(metadata or {})
            if failure is not None:
                trace_metadata.update(
                    {
                        "failure_kind": failure.kind,
                        "recovery_action": failure.recovery_action,
                        "retryable": failure.retryable,
                    }
                )
            if checkpoint_ref:
                trace_metadata["checkpoint_ref"] = checkpoint_ref
            trace = self._trace_for(stored, status=phase, producer_ts=producer_ts, metadata=trace_metadata)
            with self._transaction():
                self._update_task(stored, expected_revision)
                self._insert_trace(trace)
            return stored.model_copy(deep=True)

    def append_trace(
        self,
        task_id: str,
        *,
        expected_revision: int,
        record: TaskTraceRecord,
    ) -> TaskTraceRecord:
        with self._lock:
            current, _ = self._require_row(task_id)
            self._assert_revision(current, expected_revision)
            if current.phase in {"committed", "aborted"}:
                raise ValueError("terminal_task_mutation")
            if record.task_id != current.task_id or record.run_id != current.run_id or record.correlation_id != current.correlation_id:
                raise ValueError("trace_identity_mismatch")
            latest = self._latest_trace_sequence(task_id)
            if record.sequence != latest + 1:
                raise ValueError("trace_sequence_conflict")
            stored = current.model_copy(update={"revision": current.revision + 1}, deep=True)
            with self._transaction():
                self._update_task(stored, expected_revision)
                self._insert_trace(record)
            return record.model_copy(deep=True)

    def list_trace(self, task_id: str) -> list[TaskTraceRecord]:
        with self._lock:
            self._require_row(task_id)
            rows = self._connection.execute(
                "SELECT record_json FROM harness_task_trace WHERE task_id = ? ORDER BY sequence",
                (task_id,),
            ).fetchall()
            return [TaskTraceRecord.model_validate_json(row[0]) for row in rows]

    def recover(self, task_id: str) -> ExecutionEnvelope:
        with self._lock:
            current, _ = self._require_row(task_id)
            if current.phase in {"committed", "aborted"}:
                raise ValueError("terminal_task_recovery")
            return current.model_copy(deep=True)

    def delete(self, task_id: str) -> None:
        """Remove a task only when its authoritative domain history is gone."""
        with self._lock:
            with self._transaction():
                self._connection.execute(
                    "DELETE FROM harness_task_trace WHERE task_id = ?",
                    (task_id,),
                )
                self._connection.execute(
                    "DELETE FROM harness_tasks WHERE task_id = ?",
                    (task_id,),
                )

    def _migrate(self) -> None:
        with self._connection:
            self._connection.execute("CREATE TABLE IF NOT EXISTS harness_schema(version INTEGER PRIMARY KEY)")
            versions = [row[0] for row in self._connection.execute("SELECT version FROM harness_schema")]
            if versions and versions != [self.SCHEMA_VERSION]:
                raise ValueError(f"unsupported harness ledger schema: {versions}")
            if not versions:
                self._connection.execute("INSERT INTO harness_schema(version) VALUES (?)", (self.SCHEMA_VERSION,))
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS harness_tasks(task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, correlation_id TEXT NOT NULL, revision INTEGER NOT NULL, envelope_json TEXT NOT NULL)"
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS harness_task_trace(task_id TEXT NOT NULL, sequence INTEGER NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(task_id, sequence), FOREIGN KEY(task_id) REFERENCES harness_tasks(task_id))"
            )

    def _read_row(self, task_id: str) -> tuple[ExecutionEnvelope, int] | None:
        row = self._connection.execute(
            "SELECT envelope_json, revision FROM harness_tasks WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        envelope = ExecutionEnvelope.model_validate_json(row[0])
        if envelope.revision != int(row[1]):
            raise ValueError("harness_task_revision_corrupt")
        return envelope, int(row[1])

    def _require_row(self, task_id: str) -> tuple[ExecutionEnvelope, int]:
        row = self._read_row(task_id)
        if row is None:
            raise ValueError(f"unknown task: {task_id}")
        return row

    @staticmethod
    def _assert_revision(envelope: ExecutionEnvelope, expected_revision: int) -> None:
        if envelope.revision != expected_revision:
            raise ValueError("stale_revision")

    def _update_task(self, envelope: ExecutionEnvelope, expected_revision: int) -> None:
        result = self._connection.execute(
            "UPDATE harness_tasks SET revision = ?, envelope_json = ? WHERE task_id = ? AND revision = ?",
            (envelope.revision, self._dump(envelope), envelope.task_id, expected_revision),
        )
        if result.rowcount != 1:
            raise ValueError("stale_revision")

    def _insert_trace(self, record: TaskTraceRecord) -> None:
        self._connection.execute(
            "INSERT INTO harness_task_trace(task_id, sequence, record_json) VALUES (?, ?, ?)",
            (record.task_id, record.sequence, self._dump(record)),
        )

    def _latest_trace_sequence(self, task_id: str) -> int:
        row = self._connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) FROM harness_task_trace WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        return int(row[0])

    def _trace_for(self, envelope: ExecutionEnvelope, *, status: str, producer_ts: int, metadata: dict[str, object]) -> TaskTraceRecord:
        return TaskTraceRecord(
            sequence=self._latest_trace_sequence(envelope.task_id) + 1,
            task_id=envelope.task_id,
            run_id=envelope.run_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            stage="lifecycle",
            status=status,
            producer_ts=producer_ts,
            metadata=metadata,
        )

    @staticmethod
    def _dump(value: object) -> str:
        return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    class _Transaction:
        def __init__(self, connection: sqlite3.Connection) -> None:
            self._connection = connection

        def __enter__(self) -> sqlite3.Connection:
            self._connection.execute("BEGIN IMMEDIATE")
            return self._connection

        def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()

    def _transaction(self) -> _Transaction:
        return self._Transaction(self._connection)


__all__ = ["HarnessTaskLedger"]
