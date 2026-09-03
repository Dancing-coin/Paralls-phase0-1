"""Focused verification for the General Economy Platform C foundation."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_econom_manifest_v3.py",
        "backend/tests/test_economy_manifest_v3.py",
        "backend/tests/test_economy_platform_content.py",
        "backend/tests/test_economy_platform_catalog.py",
        "backend/tests/test_economy_platform_runtime.py",
        "backend/tests/test_economy_commerce_platform.py",
        "backend/tests/test_economy_market_platform.py",
        "backend/tests/test_economy_financial_platform.py",
        "backend/tests/test_economy_macro_platform.py",
    ]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, check=False)
    report = {
        "overall_general_economy_platform_passed": result.returncode == 0,
        "scope": "Manifest v3/platform 2.0 foundation, strict Economy content, immutable descriptors, owner-local issuance/ledger/hold/obligation/commerce/tax evidence and replay. Market, finance and macro suites join when their staged modules land.",
        "tests": tests,
        "exit_code": result.returncode,
    }
    path = ROOT / ".harness" / "verification" / "general-economy-platform-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"general_economy_platform_report={path}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
