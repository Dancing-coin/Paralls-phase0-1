from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2ak_public_project_budget_close.py",
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
            "inf2ak or public_project_budget_close",
            "--basetemp=.pytest-tmp/harness-inf2ak",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2ak-public-project-budget-close",
        "row": "INF-2AI consumed budget + INF-4AJ funded_and_executed execution -> one Economy public_project_budget_closed event",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-5000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EconomyAuthorityService only",
            "exact INF-2AI consumed budget and INF-4AJ execution sources",
            "authority-only terminal close marker",
            "no account mutation, release, refund, transfer, payment, or generic lifecycle",
            "project and facility binding plus source revision pins",
            "owner-derived idempotency and append-derived receipt",
            "full and checkpoint-tail replay",
            "zero-write for missing, private, stale, duplicate, unadmitted, or mismatched evidence",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2ak-public-project-budget-close-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2ak_report_json={artifact}")
    print(f"overall_inf2ak_public_project_budget_close_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
