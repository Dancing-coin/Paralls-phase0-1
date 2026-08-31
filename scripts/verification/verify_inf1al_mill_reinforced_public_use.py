from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf1al_mill_reinforced_public_use.py",
        "backend/tests/test_inf1aj_facility_public_use.py",
        "backend/tests/test_infra_construction_mill_reinforcement.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf1al"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf1al-mill-reinforced-public-use",
        "row": "exact completed mill_reinforced production run -> Construction public-use enabled",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing ConstructionProductionAuthority only",
            "mill_reinforced-only source partition with frozen v2 reinforcement provenance",
            "project privacy and facility/project binding",
            "verification, reinforcement, facility and stream revision pins",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail replay",
            "terminal no-disable/no-compensation",
            "no payment/material/output/permit/technology/weather/maintenance/social semantics",
            "no generic facility-kind public-use operation",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf1al-mill-reinforced-public-use-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf1al_report_json={artifact}")
    print(f"overall_inf1al_mill_reinforced_public_use_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
