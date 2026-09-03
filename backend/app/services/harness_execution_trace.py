from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from threading import RLock

from app.models.harness_execution import (
    ExecutionEnvelope,
    ExecutionPhase,
    FailureKind,
    TaskTraceRecord,
    classify_failure,
)
from app.services.harness_task_ledger import HarnessTaskLedger


_TRANSITIONS: dict[ExecutionPhase, frozenset[ExecutionPhase]] = {
    "created": frozenset({"running", "aborted"}),
    "running": frozenset({"waiting", "recovering", "committed", "failed", "aborted"}),
    "waiting": frozenset({"running", "committed", "aborted"}),
    "recovering": frozenset({"running", "failed", "aborted"}),
    "failed": frozenset({"recovering", "aborted"}),
    "committed": frozenset(),
    "aborted": frozenset(),
}


class HarnessExecutionTraceService:
    """Process-local task lifecycle and trace store; it has no authority write path."""

    _REDACT_KEYS = {"api_key", "secret", "token", "authorization", "password"}
    _FORBIDDEN_KEYS = {
        "chain_of_thought",
        "reasoning_draft",
        "hidden_state",
        "raw_private_memory",
        "private_participant_terms",
    }

    def __init__(
        self,
        storage_path: str | Path | None = None,
        *,
        ledger_path: str | Path | None = None,
    ) -> None:
        self._lock = RLock()
        self._storage_path = Path(storage_path) if storage_path is not None else None
        self._ledger = HarnessTaskLedger(ledger_path) if ledger_path is not None else None
        self._envelopes: dict[str, ExecutionEnvelope] = {}
        self._traces: dict[str, list[TaskTraceRecord]] = {}
        self._load()

    def start(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str,
        causation_id: str = "",
        policy_revision: str = "",
        authority_revision: str = "",
        max_attempts: int = 3,
    ) -> ExecutionEnvelope:
        with self._lock:
            if self._ledger is not None:
                return self._ledger.create(
                    ExecutionEnvelope(
                        task_id=task_id,
                        run_id=run_id,
                        correlation_id=correlation_id,
                        causation_id=causation_id,
                        policy_revision=policy_revision,
                        authority_revision=authority_revision,
                        max_attempts=max_attempts,
                    )
                )
            return self._start(
                task_id=task_id,
                run_id=run_id,
                correlation_id=correlation_id,
                causation_id=causation_id,
                policy_revision=policy_revision,
                authority_revision=authority_revision,
                max_attempts=max_attempts,
            )

    def _start(
        self,
        *,
        task_id: str,
        run_id: str,
        correlation_id: str,
        causation_id: str,
        policy_revision: str,
        authority_revision: str,
        max_attempts: int,
    ) -> ExecutionEnvelope:
        if task_id in self._envelopes:
            raise ValueError(f"task already exists: {task_id}")
        envelope = ExecutionEnvelope(
            task_id=task_id,
            run_id=run_id,
            correlation_id=correlation_id,
            causation_id=causation_id,
            policy_revision=policy_revision,
            authority_revision=authority_revision,
            max_attempts=max_attempts,
        )
        self._envelopes[task_id] = envelope
        self._traces[task_id] = [
            self._trace(
                envelope,
                stage="lifecycle",
                status="created",
                producer_ts=0,
                metadata={},
            )
        ]
        self._persist()
        return envelope.model_copy(deep=True)

    def transition(
        self,
        task_id: str,
        phase: ExecutionPhase,
        *,
        producer_ts: int,
        failure_kind: FailureKind | None = None,
        checkpoint_ref: str = "",
        metadata: dict[str, object] | None = None,
    ) -> ExecutionEnvelope:
        with self._lock:
            if self._ledger is not None:
                current = self._ledger.read(task_id)
                trace_metadata = self._sanitize_metadata(metadata or {})
                return self._ledger.transition(
                    task_id,
                    expected_revision=current.revision,
                    phase=phase,
                    producer_ts=producer_ts,
                    failure_kind=failure_kind,
                    checkpoint_ref=checkpoint_ref,
                    metadata=trace_metadata,
                )
            return self._transition(
                task_id,
                phase,
                producer_ts=producer_ts,
                failure_kind=failure_kind,
                checkpoint_ref=checkpoint_ref,
                metadata=metadata,
            )

    def _transition(
        self,
        task_id: str,
        phase: ExecutionPhase,
        *,
        producer_ts: int,
        failure_kind: FailureKind | None,
        checkpoint_ref: str,
        metadata: dict[str, object] | None,
    ) -> ExecutionEnvelope:
        envelope = self._require(task_id)
        if phase not in _TRANSITIONS[envelope.phase]:
            if not _TRANSITIONS[envelope.phase]:
                raise ValueError(f"task is terminal: {task_id}")
            raise ValueError(f"invalid transition: {envelope.phase} -> {phase}")
        if phase in {"running", "recovering"} and envelope.attempt >= envelope.max_attempts:
            raise ValueError(f"attempt budget exhausted: {task_id}")
        failure = classify_failure(failure_kind) if failure_kind is not None else None
        next_envelope = envelope.model_copy(
            update={
                "phase": phase,
                "attempt": envelope.attempt + (1 if phase in {"running", "recovering"} else 0),
                "checkpoint_ref": checkpoint_ref or envelope.checkpoint_ref,
                "failure": failure,
            },
            deep=True,
        )
        self._envelopes[task_id] = next_envelope
        trace_metadata: dict[str, object] = dict(metadata or {})
        if failure is not None:
            trace_metadata["failure_kind"] = failure.kind
            trace_metadata["recovery_action"] = failure.recovery_action
            trace_metadata["retryable"] = failure.retryable
        if checkpoint_ref:
            trace_metadata["checkpoint_ref"] = checkpoint_ref
        trace_metadata = self._sanitize_metadata(trace_metadata)
        self._append_trace(next_envelope, stage="lifecycle", status=phase, producer_ts=producer_ts, metadata=trace_metadata)
        self._persist()
        return next_envelope.model_copy(deep=True)

    def record(
        self,
        task_id: str,
        *,
        stage: str,
        status: str,
        producer_ts: int,
        metadata: dict[str, object] | None = None,
    ) -> TaskTraceRecord:
        with self._lock:
            if self._ledger is not None:
                current = self._ledger.read(task_id)
                sanitized = self._sanitize_metadata(metadata or {})
                sequence = len(self._ledger.list_trace(task_id)) + 1
                record = TaskTraceRecord(
                    sequence=sequence,
                    task_id=current.task_id,
                    run_id=current.run_id,
                    correlation_id=current.correlation_id,
                    causation_id=current.causation_id,
                    stage=stage,
                    status=status,
                    producer_ts=producer_ts,
                    metadata=sanitized,
                )
                return self._ledger.append_trace(
                    task_id,
                    expected_revision=current.revision,
                    record=record,
                )
            return self._record(
                task_id,
                stage=stage,
                status=status,
                producer_ts=producer_ts,
                metadata=metadata,
            )

    def _record(
        self,
        task_id: str,
        *,
        stage: str,
        status: str,
        producer_ts: int,
        metadata: dict[str, object] | None,
    ) -> TaskTraceRecord:
        envelope = self._require(task_id)
        if envelope.phase in {"committed", "aborted"}:
            raise ValueError(f"task is terminal: {task_id}")
        record = self._append_trace(
            envelope,
            stage=stage,
            status=status,
            producer_ts=producer_ts,
            metadata=self._sanitize_metadata(metadata or {}),
        )
        self._persist()
        return record.model_copy(deep=True)

    def get_envelope(self, task_id: str) -> ExecutionEnvelope:
        if self._ledger is not None:
            return self._ledger.read(task_id)
        return self._require(task_id).model_copy(deep=True)

    def close(self) -> None:
        if self._ledger is not None:
            self._ledger.close()

    def forget(self, task_id: str) -> None:
        with self._lock:
            if self._ledger is not None:
                self._ledger.delete(task_id)
                return
            self._envelopes.pop(task_id, None)
            self._traces.pop(task_id, None)
            self._persist()

    def get_trace(self, task_id: str) -> list[TaskTraceRecord]:
        if self._ledger is not None:
            return self._ledger.list_trace(task_id)
        self._require(task_id)
        return [record.model_copy(deep=True) for record in self._traces[task_id]]

    def _sanitize_metadata(self, metadata: dict[str, object]) -> dict[str, object]:
        def sanitize(value: object, key: str = "") -> object:
            normalized_key = key.lower()
            if normalized_key in self._FORBIDDEN_KEYS:
                raise ValueError(f"metadata field forbidden: {key}")
            if normalized_key in self._REDACT_KEYS or any(
                marker in normalized_key for marker in ("api_key", "access_token", "refresh_token")
            ):
                return "[REDACTED]"
            if isinstance(value, dict):
                return {str(child_key): sanitize(child_value, str(child_key)) for child_key, child_value in value.items()}
            if isinstance(value, list):
                return [sanitize(item) for item in value]
            return deepcopy(value)

        return sanitize(metadata)  # type: ignore[return-value]

    def _persist(self) -> None:
        if self._storage_path is None:
            return
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "envelopes": {task_id: envelope.model_dump(mode="json") for task_id, envelope in self._envelopes.items()},
            "traces": {
                task_id: [record.model_dump(mode="json") for record in records]
                for task_id, records in self._traces.items()
            },
        }
        temporary_path = self._storage_path.with_suffix(self._storage_path.suffix + ".tmp")
        temporary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary_path.replace(self._storage_path)

    def _load(self) -> None:
        if self._storage_path is None or not self._storage_path.exists():
            return
        raw = self._storage_path.read_text(encoding="utf-8").strip()
        if not raw:
            return
        payload = json.loads(raw)
        envelopes = payload.get("envelopes", {})
        traces = payload.get("traces", {})
        if not isinstance(envelopes, dict) or not isinstance(traces, dict):
            raise ValueError("harness task ledger shape invalid")
        self._envelopes = {
            str(task_id): ExecutionEnvelope.model_validate(value)
            for task_id, value in envelopes.items()
        }
        self._traces = {
            str(task_id): [TaskTraceRecord.model_validate(row) for row in rows]
            for task_id, rows in traces.items()
            if isinstance(rows, list)
        }

    def _require(self, task_id: str) -> ExecutionEnvelope:
        try:
            return self._envelopes[task_id]
        except KeyError as error:
            raise ValueError(f"unknown task: {task_id}") from error

    def _append_trace(
        self,
        envelope: ExecutionEnvelope,
        *,
        stage: str,
        status: str,
        producer_ts: int,
        metadata: dict[str, object],
    ) -> TaskTraceRecord:
        record = self._trace(
            envelope,
            stage=stage,
            status=status,
            producer_ts=producer_ts,
            metadata=metadata,
        )
        self._traces[envelope.task_id].append(record)
        return record

    def _trace(
        self,
        envelope: ExecutionEnvelope,
        *,
        stage: str,
        status: str,
        producer_ts: int,
        metadata: dict[str, object],
    ) -> TaskTraceRecord:
        return TaskTraceRecord(
            sequence=len(self._traces.get(envelope.task_id, [])) + 1,
            task_id=envelope.task_id,
            run_id=envelope.run_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            stage=stage,
            status=status,
            producer_ts=producer_ts,
            metadata=deepcopy(metadata),
        )


__all__ = ["HarnessExecutionTraceService"]
