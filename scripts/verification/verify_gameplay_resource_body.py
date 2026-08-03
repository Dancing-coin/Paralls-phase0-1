from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_resource_body_runtime.py",
    "backend/tests/test_skill_action_gameplay_gate.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    pytest_log = log_dir / "gameplay-resource-body-pytest.log"
    result = run_command(
        [resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES],
        project_root,
        pytest_log,
    )
    report = {
        "overall_gameplay_resource_body_passed": result.returncode == 0,
        "scope": "backend-only resource/body event projection, existing skill-path read gate, and atomic action settlement; it excludes resource reservation, status tags, skill-state writes, effective stats, transport, and Godot mirror delivery",
        "results": [
            {
                "id": "resource-body-action-gate",
                "title": "Skill-path, injury, and insufficient-stamina gates reject without events; success atomically consumes stamina and settles the action",
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(pytest_log)] if result.returncode == 0 else [],
                "notes": f"exit_code={result.returncode}",
            }
        ],
        "artifacts": {"pytest_log": str(pytest_log)},
    }
    json_path = log_dir / "gameplay-resource-body-report.json"
    md_path = log_dir / "gameplay-resource-body-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay Resource And Body Verification Report", report, "overall_gameplay_resource_body_passed")
    print(f"gameplay_resource_body_report_json={json_path}")
    print(f"gameplay_resource_body_report_md={md_path}")
    print(f"overall_gameplay_resource_body_passed={report['overall_gameplay_resource_body_passed']}")
    return 0 if report["overall_gameplay_resource_body_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
