from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    test_file = ROOT / "backend" / "tests" / "test_inf4v_production_work_contribution_acceptance.py"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(test_file), "-k", "inf4w", "--basetemp=.pytest-tmp/harness-inf4w"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf4w-production-work-order-fulfillment",
        "row": "committed INF-4V accepted work contribution -> Organization work-order fulfilled",
        "focused_tests": str(test_file.relative_to(ROOT)).replace("\\", "/"),
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "one existing Organization owner",
            "one exact INF-4V accepted source event",
            "organization-summary privacy",
            "accepted/source revision pins",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail replay",
            "terminal no-reopen/no-compensation",
            "no wage/payment/output/material/social/branch semantics",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf4w-production-work-order-fulfillment-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf4w_report_json={artifact}")
    print(f"overall_inf4w_production_work_order_fulfillment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
