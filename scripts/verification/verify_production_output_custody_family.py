from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_production_output_custody_family_blocker.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "production-output-custody-family",
        "family_ref": "production_output_custody@1",
        "status": "blocked",
        "blocker_ref": "blocker:production-output-custody-committed-facts@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "blocked family performs zero writes",
            "quantity, holder mapping, and unique destination container are not inferred",
            "no Inventory generic custody writer is added",
            "existing narrow mill custody row remains unchanged",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "production-output-custody-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"production_output_custody_family_report_json={artifact}")
    print(f"overall_production_output_custody_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
