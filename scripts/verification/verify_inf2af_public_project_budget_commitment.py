from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2af_public_project_budget_commitment.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "-k", "inf2af or public_project_budget", "--basetemp=.pytest-tmp/harness-inf2af"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2af-public-project-budget-commitment",
        "row": "exact Construction public-project step -> Economy authority-only budget commitment",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EconomyAuthorityService only",
            "fixed public-project step source",
            "fixed 12 currency:local commitment",
            "authority-only privacy",
            "no account debit/credit or inventory/material write",
            "source/economy revision pins",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail projection replay",
            "no generic payment/transfer/budget registry",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2af-public-project-budget-commitment-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2af_report_json={artifact}")
    print(f"overall_inf2af_public_project_budget_commitment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
