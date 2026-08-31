from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf3_weather_rain_resource_recovery.py",
        "backend/tests/test_infra_continuation_gate.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "-k", "inf3_weather_rain_resource or inf3_continuation_gate or catalog"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf3aa-weather-rain-water-resource-recovery",
        "row": "exact project-visible weather:rain front plus unique target-region water resource -> fixed +10 recovery",
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EcologyHazardAuthority only",
            "weather:rain front only; drought_process_advanced is not a source",
            "unique owner-derived substance:water ResourceNode selector",
            "fixed +10 recovery capped at 100",
            "project privacy, exact source/resource revisions, append receipt, and full/checkpoint-tail replay",
            "no crop, grain, inventory, payment, material, generic recovery API, fanout, or compensation",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf3aa-weather-rain-water-resource-recovery-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf3aa_report_json={artifact}")
    print(f"overall_inf3aa_weather_rain_water_resource_recovery_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
