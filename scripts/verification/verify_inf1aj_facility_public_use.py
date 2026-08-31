from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf1aj_facility_public_use.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "-k", "inf1aj or public_use", "--basetemp=.pytest-tmp/harness-inf1aj"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf1aj-facility-public-use",
        "row": "exact project-visible oven operational verification -> Construction public-use enabled",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing ConstructionProductionAuthority only",
            "oven-only source and target",
            "project privacy and facility/project binding",
            "source verification/facility/stream revision pins",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail replay",
            "terminal no-disable/no-compensation",
            "no payment/material/output/permit/technology/weather/maintenance/social semantics",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf1aj-facility-public-use-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf1aj_report_json={artifact}")
    print(f"overall_inf1aj_facility_public_use_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
