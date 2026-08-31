from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf4ap_grain_intake_activity.py",
        "backend/tests/test_inf3ab_grain_harvest_inventory_custody.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf4ap"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf4ap-grain-intake-activity",
        "row": "committed Inventory grain custody -> fixed Organization grain intake record",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "pins": {
            "source_event": "gameplay.inventory.grain_harvest_received@1",
            "source_owner": "organization:district-milling-cooperative",
            "target_owner": "organization:district-milling-cooperative",
            "target_event": "gameplay.organization.grain_intake_recorded@1",
            "item_ref": "grain:wheat@1",
            "quantity": 10,
            "privacy": "project",
        },
        "boundaries": [
            "existing OrganizationAuthority only",
            "inventory source remains owner-local truth",
            "append-derived project receipt",
            "full/checkpoint-tail replay",
            "no payment, production, transfer, attendance, social, or generic activity",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf4ap-grain-intake-activity-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf4ap_report_json={artifact}")
    print(f"overall_inf4ap_grain_intake_activity_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
