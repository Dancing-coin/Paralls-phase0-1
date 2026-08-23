import pytest
from pydantic import ValidationError

from app.models.harness_execution import ExecutionEnvelope, classify_failure
from app.services.harness_execution_trace import HarnessExecutionTraceService


def test_failure_policy_is_deterministic() -> None:
    assert classify_failure("stale_revision").recovery_action == "refresh_revision"
    assert classify_failure("transient").retryable is True
    assert classify_failure("permission_denied").retryable is False


def test_execution_envelope_rejects_empty_identity() -> None:
    with pytest.raises(ValidationError):
        ExecutionEnvelope(task_id="", run_id="run:1", correlation_id="corr:1")


def test_service_rejects_terminal_transition_and_preserves_trace() -> None:
    service = HarnessExecutionTraceService()
    service.start(task_id="task:1", run_id="run:1", correlation_id="corr:1")
    service.transition("task:1", "running", producer_ts=1)
    service.transition("task:1", "committed", producer_ts=2)
    with pytest.raises(ValueError, match="terminal"):
        service.transition("task:1", "running", producer_ts=3)
    assert [row.sequence for row in service.get_trace("task:1")] == [1, 2, 3]


def test_failure_transition_records_disposition() -> None:
    service = HarnessExecutionTraceService()
    service.start(task_id="task:2", run_id="run:2", correlation_id="corr:2")
    service.transition("task:2", "running", producer_ts=3)
    envelope = service.transition(
        "task:2",
        "failed",
        producer_ts=4,
        failure_kind="stale_revision",
    )
    assert envelope.failure is not None
    assert envelope.failure.recovery_action == "refresh_revision"
    assert service.get_trace("task:2")[-1].metadata["failure_kind"] == "stale_revision"


def test_trace_preserves_task_run_and_correlation_identity() -> None:
    service = HarnessExecutionTraceService()
    service.start(
        task_id="task:3",
        run_id="run:3",
        correlation_id="corr:3",
        causation_id="cause:3",
    )
    service.record(
        "task:3",
        stage="authority",
        status="observed",
        producer_ts=5,
        metadata={"result_ref": "result:3"},
    )
    record = service.get_trace("task:3")[-1]
    assert (record.task_id, record.run_id, record.correlation_id) == (
        "task:3",
        "run:3",
        "corr:3",
    )
    assert record.causation_id == "cause:3"
    assert record.sequence == 2


def test_service_enforces_attempt_budget() -> None:
    service = HarnessExecutionTraceService()
    service.start(task_id="task:budget", run_id="run:budget", correlation_id="corr:budget", max_attempts=1)
    service.transition("task:budget", "running", producer_ts=1)
    with pytest.raises(ValueError, match="attempt budget"):
        service.transition("task:budget", "recovering", producer_ts=2)


def test_trace_service_uses_sqlite_ledger_when_configured(tmp_path) -> None:
    path = tmp_path / "trace.sqlite3"
    service = HarnessExecutionTraceService(ledger_path=path)
    created = service.start(task_id="task:sqlite", run_id="run:sqlite", correlation_id="corr:sqlite")
    service.transition("task:sqlite", "running", producer_ts=1)
    service.record("task:sqlite", stage="authority", status="observed", producer_ts=2, metadata={"api_key": "secret"})

    reopened = HarnessExecutionTraceService(ledger_path=path)
    assert reopened.get_envelope("task:sqlite").revision == 2
    assert reopened.get_trace("task:sqlite")[-1].metadata["api_key"] == "[REDACTED]"
    assert created.revision == 0
