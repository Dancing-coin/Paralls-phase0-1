from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_GROUPS = [
    (
        "patch-contract-and-lifecycle",
        "Trusted manifest, lifecycle authority, and explicit state-group control tests pass",
        (
            "backend/tests/test_gameplay_patch_runtime.py",
            "backend/tests/test_gameplay_patch_lifecycle_authority.py",
            "backend/tests/test_state_group_lifecycle_authority.py",
        ),
    ),
    (
        "migration-replay-and-zero-write-rejection",
        "Typed migration replay, checkpoint equivalence, and pre-write rejection tests pass",
        (
            "backend/tests/test_resource_body_runtime.py",
            "backend/tests/test_gameplay_event_replay.py",
            "backend/tests/test_phase3_state_composer.py",
        ),
    ),
    (
        "post-commit-godot-projection",
        "Patch migration refreshes only the filtered Godot projection after commit",
        (
            "backend/tests/test_gameplay_event_spine.py",
            "backend/tests/test_phase3_mirror_source.py",
            "backend/tests/test_godot_gameplay_mirror_delivery.py",
            "backend/tests/test_godot_gameplay_mirror_projection.py",
        ),
    ),
    (
        "patch-rule-ir-and-capability-boundary",
        "Rule IR remains deterministic and capability-gated without a generic domain writer",
        (
            "backend/tests/test_gameplay_runtime_state.py",
            "backend/tests/test_gameplay_patch_rule_settlement.py",
        ),
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    results = []
    pytest_logs: dict[str, str] = {}
    for check_id, title, test_files in TEST_GROUPS:
        pytest_log = log_dir / f"gameplay-patch-runtime-{check_id}.log"
        result = run_command([python_exe, "-m", "pytest", "-q", *test_files], project_root, pytest_log)
        pytest_logs[check_id] = str(pytest_log)
        results.append(
            {
                "id": check_id,
                "title": title,
                "status": "proved" if result.returncode == 0 else "missing",
                "evidence": [str(pytest_log)] if result.returncode == 0 else [],
                "notes": f"exit_code={result.returncode}",
            }
        )
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_gameplay_patch_runtime_passed": overall,
        "results": results,
        "artifacts": {"pytest_logs": pytest_logs},
    }
    json_path = log_dir / "gameplay-patch-runtime-report.json"
    markdown_path = log_dir / "gameplay-patch-runtime-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "Gameplay Patch Runtime Verification Report", report, "overall_gameplay_patch_runtime_passed")
    print(f"gameplay_patch_runtime_report_json={json_path}")
    print(f"gameplay_patch_runtime_report_md={markdown_path}")
    print(f"overall_gameplay_patch_runtime_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
