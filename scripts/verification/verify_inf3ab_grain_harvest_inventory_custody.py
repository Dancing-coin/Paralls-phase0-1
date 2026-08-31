from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf3ab_grain_harvest_inventory_custody.py",
        "backend/tests/test_inf3_grain_harvest.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf3ab"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf3ab-grain-harvest-inventory-custody",
        "row": "committed project-visible grain harvest -> fixed district milling cooperative grain custody",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "pins": {
            "source_event": "gameplay.ecology.grain_harvested",
            "source_privacy": "project",
            "holder_ref": "organization:district-milling-cooperative",
            "container_ref": "container:district-milling-cooperative:grain-intake",
            "item_ref": "grain:wheat@1",
            "quantity": 10,
            "event_type": "gameplay.inventory.grain_harvest_received@1",
        },
        "boundaries": [
            "existing InventoryAuthorityService only",
            "owner-derived holder/container/item id",
            "append-derived project receipt",
            "full/checkpoint-tail Inventory projector replay",
            "unknown/private/stale/duplicate zero-write",
            "no generic harvest, transfer, payment, router, or second runtime",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf3ab-grain-harvest-inventory-custody-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf3ab_report_json={artifact}")
    print(f"overall_inf3ab_grain_harvest_inventory_custody_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
