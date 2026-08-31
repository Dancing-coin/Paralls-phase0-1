from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf3_grain_harvest.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf3-grain-harvest",
        "row": "fixed project-visible mature grain:wheat admission -> one Ecology grain_harvested event",
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EcologyHazardAuthority only",
            "fixed grain:wheat species, mature status, yield quantity 10, and plot/project binding",
            "one owner-derived Ecology grain_harvested event with grain:wheat@1 item definition",
            "project privacy, exact stream/source revision pins, append receipt, and full/checkpoint-tail replay",
            "zero-write unknown/private/stale/ambiguous/duplicate paths",
            "no Inventory writer, Economy writer, material conversion, generic harvest API, fanout, router, or compensation",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf3-grain-harvest-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf3_grain_report_json={artifact}")
    print(f"overall_inf3_grain_harvest_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
