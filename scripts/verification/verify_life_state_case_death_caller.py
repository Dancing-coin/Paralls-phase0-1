from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from common import artifact_ref, repo_root, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    test = root / "backend/tests/test_life_state_case_death_caller.py"
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", str(test)], cwd=root, capture_output=True, text=True)
    report = {
        "profile": "infra-life-state-case-death-caller",
        "overall_passed": result.returncode == 0,
        "overall_life_state_case_death_passed": result.returncode == 0,
        "focused_tests": [artifact_ref(root, test).replace("\\", "/")],
        "write_path": "explicit case-death confirmation -> CaseDeathLifeStateCaller -> CanonicalLifeStateAuthority -> GameplayEventStore.append_batch",
        "limitations": ["Does not implement Presence, Soul, incarnation, revive, or health-derived death."],
        "stdout": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
    }
    path = verification_dir(root) / "infra-life-state-case-death-caller-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "LifeState Case-Death Caller", {"results": [{"id": "case-death", "status": "proved" if report["overall_passed"] else "missing", "title": "Explicit case-death LifeState transition"}], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"life_state_case_death_report_json={path}")
    print(f"overall_life_state_case_death_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    from run_context import run_scope
    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
