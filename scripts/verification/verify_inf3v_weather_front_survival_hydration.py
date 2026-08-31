from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf3v_weather_front_survival_hydration.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "-k", "inf3v or hydration", "--basetemp=.pytest-tmp/harness-inf3v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf3v-weather-front-survival-hydration",
        "row": "exact project-visible Ecology weather:rain front -> existing Survival state:hydrated",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing EcologyHazardAuthority source and SurvivalAuthority target",
            "weather:rain only",
            "active profile-to-region assignment",
            "project privacy and source/target revision pins",
            "existing state_applied + obligation_opened vector",
            "append-derived receipt and full/checkpoint-tail replay",
            "no drought_process_advanced substitution",
            "no generic consumer/fanout/router/compensation",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf3v-weather-front-survival-hydration-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf3v_report_json={artifact}")
    print(f"overall_inf3v_weather_front_survival_hydration_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
