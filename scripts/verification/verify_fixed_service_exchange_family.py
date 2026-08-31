from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_fixed_service_exchange_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "fixed-service-exchange-family",
        "family_ref": "fixed_service_exchange@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Economy remains the ledger owner",
            "one fulfilled Contract service source derives both parties",
            "same fixed_service_exchange@1 adapter accepts multiple immutable completed-service package instances",
            "active package content fixes service, outcome, amount, currency, and policy",
            "caller cannot choose party, account, currency, price, event, or idempotency key",
            "existing append-derived settlement and authority projection replay",
            "historical public-workshop and municipal drought service exchanges remain unchanged",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "fixed-service-exchange-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"fixed_service_exchange_family_report_json={artifact}")
    print(f"overall_fixed_service_exchange_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
