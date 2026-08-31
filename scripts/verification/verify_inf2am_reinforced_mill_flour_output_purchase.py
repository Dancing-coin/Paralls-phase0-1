from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2am_reinforced_mill_flour_output_purchase.py",
        "backend/tests/test_inf1am_mill_flour_output_certification.py",
        "backend/tests/test_infra_package_declared_negotiated_exchange.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf2am"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2am-reinforced-mill-flour-output-purchase",
        "row": "INF-1AM certified reinforced mill flour output -> Inventory custody -> fixed v7 Economy purchase",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "registered_row": {
            "catalog_ref": "inf:industrial-facility-reinforced-mill-flour-output-purchase@1",
            "descriptor_ref": "descriptor:industrial-facility-reinforced-mill-flour-output-purchase@1",
            "package_revision": "package:industrial-facilities:v7",
            "source_event": "gameplay.construction_production.mill_flour_output_certified@1",
            "inventory_event": "gameplay.inventory.mill_flour_output_received@1",
            "provider_ref": "organization:district-milling-cooperative",
            "item_ref": "item:industrial-facilities:flour@1",
            "quantity": 10,
            "price_minor": 8,
            "currency_ref": "currency:local",
        },
        "boundaries": [
            "existing InventoryAuthorityService and EconomyAuthorityService only",
            "source is exact project-visible INF-1AM certification",
            "provider-held fixed container and owner-derived certified item id",
            "fixed v7 package, descriptor, binding, outcome and price pins",
            "separate project Inventory receipt and authority Economy settlement",
            "owner-derived party/account resolution and append-derived receipts",
            "full/checkpoint-tail replay and zero-write rejection",
            "terminal no-compensation purchase semantics",
            "no generic output, market, arbitrary payment, transfer or second owner",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2am-reinforced-mill-flour-output-purchase-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2am_report_json={artifact}")
    print(f"overall_inf2am_reinforced_mill_flour_output_purchase_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
