from __future__ import annotations

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from common import repo_root, resolve_godot_exe, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_embodied_harness_task.py",
    "backend/tests/test_embodied_interaction_session.py",
    "backend/tests/test_character_agent_session_store.py",
    "backend/tests/test_harness_failure_adapters.py",
    "backend/tests/test_harness_capability_store.py",
    "backend/tests/test_harness_task_ledger.py",
    "backend/tests/test_interaction_orchestration_runtime_service.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    output = verification_dir(root)
    log_path = output / "harness-embodied-task-pytest.log"
    result = run_command(
        [resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES],
        root,
        log_path,
    )
    godot_log = output / "harness-embodied-task-godot.log"
    godot_result = run_command(
        [
            resolve_python_exe(args.python_exe),
            str(root / "scripts" / "verification" / "verify_embodied_interaction_session.py"),
            "--godot-exe",
            str(resolve_godot_exe(args.godot_exe)),
            "--python-exe",
            resolve_python_exe(args.python_exe),
        ],
        root,
        godot_log,
    )
    passed = result.returncode == 0 and godot_result.returncode == 0
    results = [
        {
            "id": "real_session_authority",
            "title": "Coordinator drives the real embodied session through Gameplay authority",
            "status": "proved" if passed else "missing",
            "evidence": ["EmbodiedInteractionSessionService", "GameplayEventStore", "outbox"] if passed else [],
        },
        {
            "id": "failure_and_recovery",
            "title": "Domain failures, terminal idempotency, and persistent recovery are covered",
            "status": "proved" if passed else "missing",
            "evidence": ["FailureKind", "recovery_required", "terminal_no_duplicate"] if passed else [],
        },
        {
            "id": "capability_and_redaction",
            "title": "Capability phase ordering and trace metadata privacy are enforced",
            "status": "proved" if passed else "missing",
            "evidence": ["inspect->preflight->propose->approve->commit->verify", "metadata allowlist"] if passed else [],
        },
        {
            "id": "godot_projection_evidence",
            "title": "Safe Godot projection refs join the task trace without private payloads",
            "status": "proved" if passed else "missing",
            "evidence": ["event_id", "transaction_id", "global_sequence", "session_id"] if passed else [],
        },
        {
            "id": "focused_pytest",
            "title": "Embodied Harness task focused tests pass",
            "status": "proved" if passed else "missing",
            "evidence": [str(log_path)],
        },
    ]
    report = {
        "results": results,
        "overall_harness_embodied_task_passed": passed,
        "artifacts": {"pytest_log": str(log_path), "godot_log": str(godot_log)},
    }
    json_path = output / "harness-embodied-task-report.json"
    markdown_path = output / "harness-embodied-task-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Harness Embodied Task Verification Report", report, "overall_harness_embodied_task_passed")
    print(f"harness_embodied_task_report_json={json_path}")
    print(f"harness_embodied_task_report_md={markdown_path}")
    print(f"overall_harness_embodied_task_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
