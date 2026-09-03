"""Focused verification for the general Inventory platform."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]

def main() -> int:
    tests = [
        "backend/tests/test_inventory_platform_content.py",
        "backend/tests/test_inventory_platform_runtime.py",
        "backend/tests/test_inventory_platform_catalog.py",
        "backend/tests/test_inventory_condition_transport.py",
        "backend/tests/test_inventory_consumer_platform.py",
        "backend/tests/test_inventory_presentation.py",
        "backend/tests/test_inventory_runtime.py",
        "backend/tests/test_inventory_reservation.py",
    ]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, check=False)
    report = {"overall_inventory_generic_platform_passed": result.returncode == 0, "tests": tests, "exit_code": result.returncode, "august_inf_status": "not complete"}
    path = ROOT / ".harness" / "verification" / "inventory-generic-platform-report.json"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"inventory_generic_platform_report={path}"); return result.returncode

if __name__ == "__main__": raise SystemExit(main())
