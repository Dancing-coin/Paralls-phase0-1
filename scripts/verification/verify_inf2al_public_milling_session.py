from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf2al_public_milling_session.py",
        "backend/tests/test_inf1al_mill_reinforced_public_use.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf2al"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf2al-public-milling-session",
        "row": "exact mill_reinforced public-use -> Contract service -> Economy fixed exchange",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing ContractAuthorityService and EconomyAuthorityService only",
            "source is exact project-visible INF-1AL row with frozen v2 reinforcement provenance",
            "immutable package-industrial-facilities:v6 and adapter-verified digest pins",
            "fixed public milling service and 8 currency:local price",
            "authority-only contract/economy facts; source remains project-scoped",
            "owner-derived account resolution and append-derived receipts",
            "full/checkpoint-tail replay and zero-write rejection",
            "no generic service/payment/transfer/market/settlement authority",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf2al-public-milling-session-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf2al_report_json={artifact}")
    print(f"overall_inf2al_public_milling_session_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
