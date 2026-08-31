from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = ["backend/tests/test_facility_lifecycle_transition_family.py"]
    manifest_paths = [
        "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-bakery-v1.manifest.json",
        "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-mill-v1.manifest.json",
    ]
    manifest_evidence = []
    for relative_path in manifest_paths:
        payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
        extension = payload["platform_extension"]
        manifest_evidence.append(
            {
                "path": relative_path,
                "patch_revision_id": payload["patch_revision_id"],
                "facility_kinds": [
                    definition["typed_content"]["facility_kind"]
                    for definition in extension["package_definitions"]
                ],
            }
        )
    genericity_passed = (
        len(manifest_evidence) == 2
        and {kind for item in manifest_evidence for kind in item["facility_kinds"]}
        == {"bakery_reinforced", "mill_reinforced"}
    )
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", *tests], cwd=ROOT, capture_output=True, text=True)
    report = {
        "profile": "facility-lifecycle-transition-family",
        "family_ref": "facility_lifecycle_transition@1",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0 and genericity_passed,
        "genericity_passed": genericity_passed,
        "committed_manifest_evidence": manifest_evidence,
        "boundaries": [
            "Construction remains sole lifecycle owner",
            "two immutable content instances: mill_reinforced and bakery_reinforced active -> decommissioned",
            "caller cannot select target lifecycle, owner, stream, event, privacy, receipt or compensation",
            "existing facility_decommissioned event and append_batch spine",
            "source privacy/revision/idempotency/full checkpoint-tail replay",
            "historical reinforced-mill decommission remains a compatibility row",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "facility-lifecycle-transition-family-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"facility_lifecycle_transition_family_report_json={artifact}")
    print(f"overall_facility_lifecycle_transition_family_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
