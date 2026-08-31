from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2ah_public_project_budget_reservation.py",
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
            "inf2ah or public_project_budget_reservation",
            "--basetemp=.pytest-tmp/harness-inf2ah-reservation",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2ah-public-project-budget-reservation",
        "row": "INF-2AF committed public-project budget -> one owner-derived Economy budget reservation",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-5000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EconomyAuthorityService only",
            "exact INF-2AF public-project commitment source",
            "committed acquisition owner derives exactly one currency:local account",
            "fixed 12-unit budget_reserved event",
            "authority-only privacy",
            "Economy and facility stream revision pins in one append batch",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail reservation projection replay",
            "zero-write for missing, multiple, stale, private, mismatched, or insufficient account evidence",
            "no generic budget, payment, transfer, release, reimbursement, or settlement API",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2ah-public-project-budget-reservation-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2ah_report_json={artifact}")
    print(f"overall_inf2ah_public_project_budget_reservation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
