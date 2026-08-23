from pathlib import Path

import pytest

from app.models.harness_execution import ExecutionEnvelope, TaskTraceRecord
from app.services.harness_task_ledger import HarnessTaskLedger


def _envelope(task_id: str = "task:ledger") -> ExecutionEnvelope:
    return ExecutionEnvelope(
        task_id=task_id,
        run_id=f"run:{task_id}",
        correlation_id=f"corr:{task_id}",
        max_attempts=3,
    )


def test_sqlite_ledger_restarts_with_envelope_and_trace(tmp_path: Path) -> None:
    path = tmp_path / "harness.sqlite3"
    ledger = HarnessTaskLedger(path)
    created = ledger.create(_envelope())
    running = ledger.transition(
        "task:ledger",
        expected_revision=created.revision,
        phase="running",
        producer_ts=1,
    )
    ledger.append_trace(
        "task:ledger",
        expected_revision=running.revision,
        record=TaskTraceRecord(
            sequence=3,
            task_id="task:ledger",
            run_id="run:task:ledger",
            correlation_id="corr:task:ledger",
            stage="authority",
            status="observed",
            producer_ts=1,
        ),
    )
    reopened = HarnessTaskLedger(path)

    assert reopened.read("task:ledger").phase == "running"
    assert reopened.read("task:ledger").revision == 2
    assert [row.sequence for row in reopened.list_trace("task:ledger")] == [1, 2, 3]


def test_ledger_rejects_stale_transition_without_mutation(tmp_path: Path) -> None:
    ledger = HarnessTaskLedger(tmp_path / "harness.sqlite3")
    created = ledger.create(_envelope())
    ledger.transition("task:ledger", expected_revision=created.revision, phase="running", producer_ts=1)

    with pytest.raises(ValueError, match="stale_revision"):
        ledger.transition("task:ledger", expected_revision=created.revision, phase="aborted", producer_ts=2)

    assert ledger.read("task:ledger").phase == "running"
    assert ledger.read("task:ledger").revision == 1


def test_ledger_create_is_idempotent_for_same_identity_and_rejects_changed_identity(tmp_path: Path) -> None:
    ledger = HarnessTaskLedger(tmp_path / "harness.sqlite3")
    first = ledger.create(_envelope())
    replay = ledger.create(_envelope())
    assert replay == first

    with pytest.raises(ValueError, match="task_identity_conflict"):
        ledger.create(_envelope().model_copy(update={"run_id": "run:changed"}))


def test_ledger_rejects_terminal_mutation_and_recovery_reexecution(tmp_path: Path) -> None:
    ledger = HarnessTaskLedger(tmp_path / "harness.sqlite3")
    created = ledger.create(_envelope())
    running = ledger.transition("task:ledger", expected_revision=created.revision, phase="running", producer_ts=1)
    committed = ledger.transition("task:ledger", expected_revision=running.revision, phase="committed", producer_ts=2)

    with pytest.raises(ValueError, match="terminal"):
        ledger.transition("task:ledger", expected_revision=committed.revision, phase="running", producer_ts=2)
    with pytest.raises(ValueError, match="terminal"):
        ledger.recover("task:ledger")


def test_delete_removes_orphaned_task_and_trace(tmp_path: Path) -> None:
    ledger = HarnessTaskLedger(tmp_path / "harness.sqlite3")
    created = ledger.create(_envelope("task:orphan"))
    ledger.transition("task:orphan", expected_revision=created.revision, phase="running", producer_ts=1)
    ledger.delete("task:orphan")

    with pytest.raises(ValueError, match="unknown task"):
        ledger.read("task:orphan")
