from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_bounded_project_budget_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "bounded-project-budget-family",
        "family_ref": "bounded_project_budget@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Economy remains sole budget owner",
            "commitment, reservation, consumption and close derive project/account/currency/amount from committed evidence",
            "fixed authority-only lifecycle and no compensation",
            "owner-derived idempotency, append-derived receipt, full/checkpoint-tail replay",
            "historical INF-2AF/2AH/2AI/2AK rows remain unchanged",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "bounded-project-budget-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"bounded_project_budget_family_report_json={artifact}")
    print(f"overall_bounded_project_budget_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
