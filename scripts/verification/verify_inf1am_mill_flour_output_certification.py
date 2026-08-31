from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf1am_mill_flour_output_certification.py",
        "backend/tests/test_infra_construction_mill_reinforcement.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf1am"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf1am-mill-flour-output-certification",
        "row": "exact active mill_reinforced facility + completed fixed mill-flour run -> Construction flour output certificate",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "registered_row": {
            "catalog_ref": "inf:construction-reinforced-mill-flour-output-certification@1",
            "descriptor_ref": "descriptor:construction-reinforced-mill-flour-output-certification@1",
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "event_type": "gameplay.construction_production.mill_flour_output_certified@1",
            "projection_scope": "project",
            "recipe_ref": "recipe:industrial-facilities:mill-flour@1",
            "output_item": "item:industrial-facilities:flour@1",
            "quantity": 10,
        },
        "boundaries": [
            "existing ConstructionProductionAuthority only",
            "frozen v2 mill -> mill_reinforced provenance is source evidence",
            "project privacy and facility/project binding",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail replay",
            "duplicate/change/revision/privacy/source zero-write rejection",
            "no Inventory, Economy, material, payment, delivery, retry, reversal, compensation, fanout, or generic output API",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf1am-mill-flour-output-certification-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf1am_report_json={artifact}")
    print(f"overall_inf1am_mill_flour_output_certification_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
