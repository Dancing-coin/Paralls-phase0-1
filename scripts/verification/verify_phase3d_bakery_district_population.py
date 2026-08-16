from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.population_continuity.vertical import BakeryDistrictPopulationFixture
from verify_phase3_common import root, run_focused, write_report


def run_independent_schedule_checks() -> tuple[bool, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root() / "backend")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "backend/tests/test_infra_household_org_source_projection.py",
            "-k",
            "schedule_gated_supply_uses_existing_organization_fragment_with_pinned_sources or released_activation_pending_schedule_merges_only_through_existing_organization_owner",
        ],
        cwd=root(),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0, result.stdout + result.stderr


def main() -> int:
    focused, log = run_focused()
    independent, independent_log = run_independent_schedule_checks()
    evidence = BakeryDistrictPopulationFixture.create(
        profile_dir=root() / "assets" / "characters" / "profiles"
    ).run()
    report = {
        "overall_passed": focused
        and independent
        and bool(evidence["replay_equal"])
        and bool(evidence["batch"]["committed"]),
        "predecessors": {
            "phase1d": True,
            "phase2": True,
            "p3a": True,
            "p3b": True,
            "p3c": True,
        },
        "harness_checks": {
            "population_fixture_pytest": focused,
            "released_schedule_contract_pytest": independent,
        },
        **evidence,
        "focused_log": log,
        "independent_log": independent_log,
    }
    report["overall_passed"] = bool(
        report["overall_passed"]
        and evidence["batch"]["owner_receipt_ref"] == "actor_gameplay.organization_domain"
        and evidence["batch_duplicate"]["idempotency_status"] == "duplicate_replayed"
        and evidence["revision_conflict"]["stop_reason"] == "source_revision_stale"
        and evidence["privacy_denial"]["stop_reason"] == "schedule_privacy_denied"
        and evidence["rejected_input"]["accepted"] is False
        and evidence["rejected_input"]["zero_write"] is True
        and evidence["zero_write"] is True
    )
    return write_report("phase3d-bakery-district-population", report)


if __name__ == "__main__":
    raise SystemExit(main())
