from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.models.harness_execution import classify_failure
from app.services.harness_execution_trace import HarnessExecutionTraceService
from common import (
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


TEST_FILES = ["backend/tests/test_harness_execution_contract.py"]


def _result(result_id: str, title: str, passed: bool, evidence: list[str]) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if passed else "missing",
        "evidence": evidence if passed else [],
    }


def main() -> int:
    project_root = repo_root()
    output = verification_dir(project_root)
    pytest_log = output / "harness-execution-contract-pytest.log"
    pytest_result = run_command(
        [resolve_python_exe(None), "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )

    service = HarnessExecutionTraceService()
    service.start(
        task_id="task:harness-contract",
        run_id="run:harness-contract",
        correlation_id="corr:harness-contract",
        causation_id="cause:harness-contract",
    )
    service.transition("task:harness-contract", "running", producer_ts=1)
    service.record(
        "task:harness-contract",
        stage="verification",
        status="observed",
        producer_ts=2,
        metadata={"check": "contract"},
    )
    service.transition("task:harness-contract", "committed", producer_ts=3)
    terminal_guard = False
    try:
        service.transition("task:harness-contract", "running", producer_ts=4)
    except ValueError:
        terminal_guard = True

    expected_actions = {
        "transient": "retry",
        "invalid_input": "repair_input",
        "permission_denied": "request_approval",
        "constraint_conflict": "replan",
        "dependency_missing": "wait_dependency",
        "stale_revision": "refresh_revision",
        "unknown": "abort",
    }
    failure_policy = all(
        classify_failure(kind).recovery_action == action
        for kind, action in expected_actions.items()
    )
    trace = service.get_trace("task:harness-contract")
    trace_correlation = (
        len(trace) == 4
        and all(record.task_id == "task:harness-contract" for record in trace)
        and all(record.run_id == "run:harness-contract" for record in trace)
        and all(record.correlation_id == "corr:harness-contract" for record in trace)
        and [record.sequence for record in trace] == [1, 2, 3, 4]
    )

    results = [
        _result(
            "pytest_contract",
            "Typed execution contract focused tests pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "lifecycle_transitions",
            "Declared lifecycle transitions accept a committed task",
            trace[-1].status == "committed" if trace else False,
            ["task:harness-contract"],
        ),
        _result(
            "failure_policy",
            "Every failure kind maps to a deterministic recovery action",
            failure_policy,
            sorted(expected_actions),
        ),
        _result(
            "terminal_guard",
            "Terminal tasks reject later transitions",
            terminal_guard,
            ["committed -> running rejected"],
        ),
        _result(
            "trace_correlation",
            "Trace records preserve task/run/correlation identity and sequence",
            trace_correlation,
            ["task_id", "run_id", "correlation_id", "sequence"],
        ),
    ]
    report = {
        "results": results,
        "overall_harness_execution_contract_passed": all(
            result["status"] == "proved" for result in results
        ),
    }
    json_path = output / "harness-execution-contract-report.json"
    markdown_path = output / "harness-execution-contract-report.md"
    write_json(json_path, report)
    write_markdown(
        markdown_path,
        "Harness Execution Contract Verification Report",
        report,
        "overall_harness_execution_contract_passed",
    )
    print(f"harness_execution_contract_report_json={json_path}")
    print(f"harness_execution_contract_report_md={markdown_path}")
    print(
        "overall_harness_execution_contract_passed="
        f"{report['overall_harness_execution_contract_passed']}"
    )
    return 0 if report["overall_harness_execution_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
