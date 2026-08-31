from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_closed_generic_gameplay_families_verifier_reports_family_matrix_and_blocker() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_closed_generic_gameplay_families.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(
        (ROOT / ".harness" / "verification" / "closed-generic-gameplay-families-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["matrix_closure_passed"] is True
    assert report["foundation_matrix_closure_complete"] is True
    assert report["family_count"] == 12
    assert (
        report["generic_implemented_family_count"]
        + report["bounded_adapter_family_count"]
        + report["blocked_family_count"]
        == 12
    )
    assert report["blocked_family_count"] == 0
    assert report["design_only_family_count"] == 0
    assert report["bounded_family_blocker_closure_passed"] is True
    assert report["generic_refactoring_complete"] is True
    assert report["goal_level_status"].startswith("foundation_matrix_closure_complete;")
    assert set(report["genericity_blocker_family_refs"]) == set()
    assert report["generic_implemented_family_count"] == 12
    assert report["bounded_adapter_family_count"] == 0
    assert "facility_lifecycle_transition@1" in report["genericity_evidence_family_refs"]
    assert report["genericity_tests_passed"] is True
    assert report["committed_manifest_digests_valid"] is True
    assert report["committed_manifest_bindings_valid"] is True
    assert report["bounded_blocker_records_complete"] is True
    assert report["committed_manifest_evidence"]["facility_lifecycle_transition@1"] == [
        "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-bakery-v1.manifest.json",
        "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-mill-v1.manifest.json",
    ]
    assert report["custody_blocker"]["blocker_ref"] == "blocker:production-output-custody-committed-facts@1"
    assert report["custody_blocker_status"] == "resolved"
    assert report["custody_resolution"]["adapter_ref"] == "InventoryAuthorityService.settle_production_output_custody"
