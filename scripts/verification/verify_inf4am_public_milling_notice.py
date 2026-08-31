from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf4am_public_milling_notice.py",
        "backend/tests/test_inf4al_public_milling_activity.py",
        "backend/tests/test_inf2al_public_milling_session.py",
        "backend/tests/test_infra_governed_authority_contract_catalog.py",
    ]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf4am"], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "inf4am-public-milling-notice",
        "row": "exact INF-4AL milling activity -> Government public milling notice",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing GovernmentAuthority only",
            "acquisition-derived jurisdiction and fixed public-notice stream",
            "exact INF-4AL project-visible milling activity source",
            "project privacy and facility/project binding",
            "owner-derived idempotency and append-derived receipt",
            "full/checkpoint-tail notice replay",
            "no permit, certificate, payment, attendance, social, population, or generic notification semantics",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf4am-public-milling-notice-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf4am_report_json={artifact}")
    print(f"overall_inf4am_public_milling_notice_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
