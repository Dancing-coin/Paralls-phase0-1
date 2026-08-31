from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_facility_identity_upgrade_family.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "facility-identity-upgrade-family",
        "family_ref": "facility_identity_upgrade@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "Construction remains sole truth owner",
            "typed package source/target slots only",
            "caller cannot choose target, owner, stream, event, privacy, receipt or compensation",
            "existing facility_transformed event and append_batch spine",
            "exact source/revision/privacy/idempotency and full/checkpoint-tail replay",
            "historical bakery/mill/oven narrow rows remain unchanged",
        ],
        "genericity_evidence": {
            "dual_content_test": "backend/tests/test_facility_identity_upgrade_family.py::test_identity_upgrade_family_consumes_multiple_admitted_content_instances_through_one_adapter",
            "active_package_revisions": [
                "package:facility-upgrade-demo@1",
                "package:facility-upgrade-mill-demo@1",
            ],
            "committed_manifest_paths": [
                "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-identity-upgrade/package-facility-identity-upgrade-demo-v1.manifest.json",
                "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-identity-upgrade/package-facility-identity-upgrade-mill-demo-v1.manifest.json",
            ],
        },
    }
    artifact = ROOT / ".harness" / "verification" / "facility-identity-upgrade-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"facility_identity_upgrade_family_report_json={artifact}")
    print(f"overall_facility_identity_upgrade_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
