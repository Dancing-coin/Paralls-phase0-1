"""Focused verification for the general Ecology platform rollout."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_ecology_platform_content.py",
        "backend/tests/test_ecology_platform_runtime.py",
        "backend/tests/test_ecology_hazard_platform.py",
        "backend/tests/test_ecology_consumer_platform.py",
        "backend/tests/test_ecology_presentation.py",
        "backend/tests/test_infra_ecology_disaster.py",
        "backend/tests/test_infra_ecology_drought_process.py",
        "backend/tests/test_infra_ecology_weather_front_propagation.py",
        "backend/tests/test_infra_ecology_weather_front_event_derived_planner.py",
    ]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, check=False)
    report = {
        "overall_ecology_generic_platform_passed": result.returncode == 0,
        "scope": "v3/platform 2.0 typed ecology content, region/grid owner runtime, seven typed hazard lifecycle, bounded propagation, six read-only owner-bound consumer admissions, and legacy Ecology INF regressions",
        "tests": tests,
        "exit_code": result.returncode,
        "august_inf_status": "not complete",
    }
    path = ROOT / ".harness" / "verification" / "ecology-generic-platform-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ecology_generic_platform_report={path}")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
