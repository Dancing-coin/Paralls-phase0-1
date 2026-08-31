from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_harvest_to_custody_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "harvest-to-custody-family",
        "family_ref": "harvest_to_custody@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Ecology harvest is the only source owner",
            "Inventory remains custody owner",
            "only the committed grain:wheat@1 source/content row is executable",
            "no committed second harvest manifest/source pair exists; synthetic test mutations are not evidence",
            "harvest_to_custody@1 remains bounded_adapter until two immutable manifest/source pairs are committed",
            "caller cannot choose custody coordinates",
            "existing grain_harvest_received@1 event, append-derived receipt, and replay readers",
            "historical INF-3AB row remains unchanged",
            "production_output_custody@1 remains separately blocked",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "harvest-to-custody-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"harvest_to_custody_family_report_json={artifact}")
    print(f"overall_harvest_to_custody_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
