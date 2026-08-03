from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "gameplay-status-tags-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", "backend/tests/test_status_tags.py"], root, log)
    report = {
        "overall_gameplay_status_tags_passed": result.returncode == 0,
        "scope": "backend-only status-tag registry, lifecycle authority events, stack limits, exclusivity, and deterministic replay; it excludes refresh, durations, modifier templates, transport, and Godot mirror delivery",
        "results": [{"id": "status-tag-lifecycle", "title": "Explicit apply/remove/expire lifecycle, stack limits, and exclusivity reject safely", "status": "proved" if result.returncode == 0 else "missing", "evidence": [str(log)] if result.returncode == 0 else [], "notes": f"exit_code={result.returncode}"}],
        "artifacts": {"pytest_log": str(log)},
    }
    json_path = verification_dir(root) / "gameplay-status-tags-report.json"
    md_path = verification_dir(root) / "gameplay-status-tags-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay Status Tags Verification Report", report, "overall_gameplay_status_tags_passed")
    print(f"overall_gameplay_status_tags_passed={report['overall_gameplay_status_tags_passed']}")
    return 0 if report["overall_gameplay_status_tags_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
