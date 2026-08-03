from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_adventure_basic_reference.py",
    "backend/tests/test_adventure_basic_scenario1.py",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log_dir = verification_dir(root)
    pytest_log = log_dir / "adventure-basic-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], root, pytest_log)
    report = {
        "overall_adventure_basic_passed": result.returncode == 0,
        "scope": "digest-valid governed adventure-basic manifest plus the backend-only Scenario 1 fixed-offer purchase/equip composition; it does not prove Patch activation, replay, mirror/Godot, body/resource, storage-ring, property, or debt scenarios",
        "results": [
            {
                "id": "manifest-baseline",
                "title": "Adventure-basic manifest is strict, trusted-format, and digest-valid before activation; Scenario 1 reuses existing fixed-offer and equipment authorities",
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(pytest_log)] if result.returncode == 0 else [],
                "notes": f"exit_code={result.returncode}",
            }
        ],
        "artifacts": {"pytest_log": str(pytest_log)},
    }
    json_path = log_dir / "adventure-basic-report.json"
    markdown_path = log_dir / "adventure-basic-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Adventure Basic Verification Report", report, "overall_adventure_basic_passed")
    print(f"adventure_basic_report_json={json_path}")
    print(f"adventure_basic_report_md={markdown_path}")
    print(f"overall_adventure_basic_passed={result.returncode == 0}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
