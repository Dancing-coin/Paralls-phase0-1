from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_gameplay_patch_runtime.py",
    "backend/tests/test_gameplay_patch_lifecycle_authority.py",
    "backend/tests/test_state_group_lifecycle_authority.py",
    "backend/tests/test_gameplay_runtime_state.py",
    "backend/tests/test_resource_body_runtime.py",
    "backend/tests/test_gameplay_patch_rule_settlement.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    pytest_log = log_dir / "gameplay-patch-runtime-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    report = {
        "overall_gameplay_patch_runtime_passed": result.returncode == 0,
        "results": [
            {
                "id": "focused-pytest-pass",
                "title": "Gameplay patch runtime pytest suite passes",
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(pytest_log)] if result.returncode == 0 else [],
                "notes": f"exit_code={result.returncode}",
            }
        ],
        "artifacts": {"pytest_log": str(pytest_log)},
    }
    json_path = log_dir / "gameplay-patch-runtime-report.json"
    markdown_path = log_dir / "gameplay-patch-runtime-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Gameplay Patch Runtime Verification Report", report, "overall_gameplay_patch_runtime_passed")
    print(f"gameplay_patch_runtime_report_json={json_path}")
    print(f"gameplay_patch_runtime_report_md={markdown_path}")
    print(f"overall_gameplay_patch_runtime_passed={result.returncode == 0}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
