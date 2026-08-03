from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "gameplay-effective-stats-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", "backend/tests/test_effective_stats.py", "backend/tests/test_modifier_runtime.py"], root, log)
    report = {
        "overall_gameplay_effective_stats_passed": result.returncode == 0,
        "scope": "backend-only deterministic effective-stat resolution plus replay of registered equipment modifier sources; it excludes generic source lifecycle, transport, and Godot mirror delivery",
        "results": [{"id": "effective-stat-resolution", "title": "Canonical modifier ordering, source replay, conditional rejection, stacking, and unresolved conflicts", "status": "proved" if result.returncode == 0 else "missing", "evidence": [str(log)] if result.returncode == 0 else [], "notes": f"exit_code={result.returncode}"}],
        "artifacts": {"pytest_log": str(log)},
    }
    json_path = verification_dir(root) / "gameplay-effective-stats-report.json"
    md_path = verification_dir(root) / "gameplay-effective-stats-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay Effective Stats Verification Report", report, "overall_gameplay_effective_stats_passed")
    print(f"overall_gameplay_effective_stats_passed={report['overall_gameplay_effective_stats_passed']}")
    return 0 if report["overall_gameplay_effective_stats_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
