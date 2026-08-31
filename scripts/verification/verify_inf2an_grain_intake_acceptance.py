from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2an_grain_intake_acceptance.py",
        "backend/tests/test_inf4ap_grain_intake_activity.py",
        "backend/tests/test_inf3ab_grain_harvest_inventory_custody.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf2an"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2an-grain-intake-acceptance",
        "row": "committed project-visible Organization grain intake -> fixed Economy acceptance marker",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "pins": {
            "source_event": "gameplay.organization.grain_intake_recorded@1",
            "source_privacy": "project",
            "source_owner": "actor_gameplay.organization_domain",
            "target_owner": "actor_gameplay.economy_domain",
            "target_stream": "gameplay:economy",
            "event_type": "gameplay.economy.grain_intake_accepted@1",
            "item_ref": "grain:wheat@1",
            "quantity": 10,
            "privacy": "authority_only",
            "terminal": "v1_terminal_no_compensation",
        },
        "boundaries": [
            "existing OrganizationAuthority source and EconomyAuthorityService target only",
            "source organization/inventory provenance, project/plot binding, and stream-head revisions are fixed",
            "append-derived authority receipt",
            "full/checkpoint-tail Economy projection replay",
            "unknown/private/stale/duplicate/changed-duplicate zero-write",
            "no debit, credit, payment, transfer, pricing, router, registry, or second runtime",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2an-grain-intake-acceptance-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2an_report_json={artifact}")
    print(f"overall_inf2an_grain_intake_acceptance_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
