from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST = "backend/tests/test_inf2ao_production_output_market_eligibility.py"


def main() -> int:
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", TEST], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "inf2ao-production-output-market-eligibility",
        "family_ref": "inf-2ao-production-output-market-eligibility@1",
        "focused_tests": [TEST],
        "test_exit_code": result.returncode,
        "test_output": (result.stdout + result.stderr)[-4000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Economy owns one authority-only eligibility marker",
            "source is committed Inventory production_output_custody only",
            "quantity/item/holder/container/project derive from source",
            "no account mutation, amount, currency, price, payment, transfer or market order",
            "append-derived receipt and full/checkpoint-tail projection",
            "unknown/private/stale/forged/duplicate sources fail closed before append",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2ao-production-output-market-eligibility-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2ao_production_output_market_eligibility_report_json={artifact}")
    print(f"overall_inf2ao_production_output_market_eligibility_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
