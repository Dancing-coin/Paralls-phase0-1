from __future__ import annotations

import argparse

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_ability_runtime.py", "backend/tests/test_skill_action_gameplay_gate.py"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    log = verification_dir(root) / "gameplay-ability-affordance-pytest.log"
    result = run_command([resolve_python_exe(args.python_exe), "-m", "pytest", "-q", *TEST_FILES], root, log)
    report = {
        "overall_gameplay_ability_affordance_passed": result.returncode == 0,
        "scope": "backend proof for event-derived stable ability state and read-only body/resource affordance resolution; it excludes promotion, equipment/inventory predicates, transport, and Godot mirror delivery",
        "results": [{"id": "ability-affordance", "title": "Stable ability truth and momentary affordance remain separate", "status": "proved" if result.returncode == 0 else "missing", "evidence": [str(log)] if result.returncode == 0 else [], "notes": f"exit_code={result.returncode}"}],
        "artifacts": {"pytest_log": str(log)},
    }
    json_path = verification_dir(root) / "gameplay-ability-affordance-report.json"
    md_path = verification_dir(root) / "gameplay-ability-affordance-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Gameplay Ability Affordance Verification Report", report, "overall_gameplay_ability_affordance_passed")
    print(f"overall_gameplay_ability_affordance_passed={report['overall_gameplay_ability_affordance_passed']}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
