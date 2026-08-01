from __future__ import annotations

import argparse
from pathlib import Path

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_gameplay_event_store_contract.py",
    "backend/tests/test_gameplay_event_replay.py",
    "backend/tests/test_gameplay_event_spine.py",
]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": check_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def _gameplay_bus_publish_is_dispatcher_scoped(project_root: Path) -> bool:
    gameplay_dir = project_root / "backend" / "app" / "gameplay"
    if not gameplay_dir.exists():
        return False
    offenders: list[str] = []
    for path in gameplay_dir.rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if ".publish(" in text and path.name != "dispatcher.py":
            offenders.append(str(path.relative_to(project_root)))
    return offenders == []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "gameplay-foundation-event-spine-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    scoped_publish = _gameplay_bus_publish_is_dispatcher_scoped(project_root)
    results = [
        _result("focused-pytest-pass", "Gameplay event spine contract, replay, and dispatcher tests pass", pytest_result.returncode == 0, [str(pytest_log)], f"exit_code={pytest_result.returncode}"),
        _result("dispatcher-only-publish-scope", "Gameplay package scopes authority bus publish to the after-commit dispatcher", scoped_publish, [str(pytest_log)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_gameplay_foundation_event_spine_passed": overall,
        "embodied_phase_6_gate": "satisfied" if overall else "blocked",
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log)},
    }
    json_path = log_dir / "gameplay-foundation-event-spine-report.json"
    md_path = log_dir / "gameplay-foundation-event-spine-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay Foundation Event Spine Verification Report", report, "overall_gameplay_foundation_event_spine_passed")
    print(f"gameplay_foundation_event_spine_report_json={json_path}")
    print(f"gameplay_foundation_event_spine_report_md={md_path}")
    print(f"overall_gameplay_foundation_event_spine_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
