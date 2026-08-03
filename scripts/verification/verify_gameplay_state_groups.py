from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_gameplay_runtime_state.py",
    "backend/tests/test_state_group_lifecycle_authority.py",
    "backend/tests/test_state_group_views.py",
    "backend/tests/test_state_group_sync.py",
    "backend/tests/test_phase3_state_composer.py",
]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": check_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "gameplay-state-groups-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    results = [
        _result(
            "minimum-runtime-state-core",
            "StateGroupRegistry, authority lifecycle batches, lifecycle projection, Phase 3 read-only composition, filtered views, and backend-only snapshot/delta tests pass",
            pytest_result.returncode == 0,
            [str(pytest_log)],
            f"exit_code={pytest_result.returncode}",
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_gameplay_state_groups_passed": overall,
        "scope": "registry, versioned eligibility catalog compilation, explicit-context authority lifecycle batches, event-derived lifecycle read model, Phase 3 read-only composition, policy-filtered authority/Godot/mind/debug views, and backend-only exact-base snapshot/delta reconstruction; policy activation loading, persistent replay rebuild, transport delivery, and Godot mirror transport are not covered",
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log)},
    }
    json_path = log_dir / "gameplay-state-groups-report.json"
    md_path = log_dir / "gameplay-state-groups-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay State Groups Verification Report", report, "overall_gameplay_state_groups_passed")
    print(f"gameplay_state_groups_report_json={json_path}")
    print(f"gameplay_state_groups_report_md={md_path}")
    print(f"overall_gameplay_state_groups_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
