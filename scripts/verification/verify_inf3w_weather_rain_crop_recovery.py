from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf3w_weather_rain_crop_recovery.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "-k", "inf3w or rain_crop_recovery"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf3w-weather-rain-crop-recovery",
        "row": "exact project-visible weather:rain front plus unique damaged crop -> Ecology fixed +5 health recovery",
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EcologyHazardAuthority only",
            "weather:rain front only; drought_process_advanced is not a source",
            "unique owner-derived damaged crop selector",
            "fixed +5 health recovery capped at 100",
            "project privacy, exact source/crop revisions, append receipt, and full/checkpoint-tail replay",
            "no fanout, inventory, output, payment, material, generic recovery API, or compensation",
        ],
    }
    path = ROOT / ".harness" / "verification" / "inf3w-weather-rain-crop-recovery-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf3w_report_json={path}")
    print(f"overall_inf3w_weather_rain_crop_recovery_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
