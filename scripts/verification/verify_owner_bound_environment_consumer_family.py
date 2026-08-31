from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_owner_bound_environment_consumer_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "owner-bound-environment-consumer-family",
        "family_ref": "owner_bound_environment_consumer@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Survival remains target-state owner",
            "typed source/state/effect content is admitted through the package binding",
            "weather source and region assignment remain committed evidence",
            "caller cannot choose actor, stream, event, privacy, receipt or idempotency",
            "existing narrow weather rows remain compatibility paths",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "owner-bound-environment-consumer-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"owner_bound_environment_consumer_family_report_json={artifact}")
    print(f"overall_owner_bound_environment_consumer_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
