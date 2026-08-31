from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2ai_public_project_budget_consumption.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *tests,
            "-k",
            "inf2ai or public_project_budget_consumption",
            "--basetemp=.pytest-tmp/harness-inf2ai",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2ai-public-project-budget-consumption",
        "row": "INF-4AG public-workshop activity + INF-2AH budget_reserved -> one Economy budget_consumed event",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-5000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EconomyAuthorityService only",
            "exact INF-4AG activity and INF-2AH reservation sources",
            "fixed 12 currency:local consumption",
            "authority-only privacy",
            "source revision pins and replayable checkpoint-tail projection",
            "owner-derived idempotency and append-derived receipt",
            "zero-write for missing, private, stale, duplicate, or mismatched evidence",
            "no generic budget, payment, transfer, release, refund, or compensation API",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2ai-public-project-budget-consumption-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2ai_report_json={artifact}")
    print(f"overall_inf2ai_public_project_budget_consumption_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
