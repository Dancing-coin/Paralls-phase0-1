from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_domain_acceptance_marker_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "domain-acceptance-marker-family",
        "family_ref": "domain_acceptance_marker@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Organization remains acceptance-marker owner",
            "one committed Inventory grain custody source only",
            "organization/item/container/quantity derive from source and fixed owner row",
            "caller cannot select owner, marker, quantity, stream, event, privacy, or idempotency",
            "existing grain_intake_recorded@1 append-derived receipt and replay",
            "historical INF-4AP row remains unchanged",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "domain-acceptance-marker-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"domain_acceptance_marker_family_report_json={artifact}")
    print(f"overall_domain_acceptance_marker_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
