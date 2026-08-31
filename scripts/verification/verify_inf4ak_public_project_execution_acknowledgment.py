from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf4ak_public_project_execution_acknowledgment.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "-k", "inf4ak or public_project_execution_acknowledgment"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf4ak-public-project-execution-acknowledgment",
        "row": "INF-4AJ funded_and_executed -> one Government authority-only administrative acknowledgment",
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing GovernmentAuthority only",
            "exact project-visible Organization execution and authority-only Economy provenance",
            "fixed derived jurisdiction Government stream",
            "authority-only privacy and terminal acknowledgment",
            "owner-derived idempotency, append receipt, and full/checkpoint-tail replay",
            "no permit, payment, material, output, attendance, social, population, or generic project lifecycle",
        ],
    }
    path = ROOT / ".harness" / "verification" / "inf4ak-public-project-execution-acknowledgment-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf4ak_report_json={path}")
    print(f"overall_inf4ak_public_project_execution_acknowledgment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
