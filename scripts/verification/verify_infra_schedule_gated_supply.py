from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_household_org_source_projection.py"
    cases = {
        "combined_planner_source_pins": "test_world_input_planner_preserves_social_household_and_organization_pins_without_merging_work",
        "schedule_owner_fragment_settlement": "test_schedule_gated_supply_uses_existing_organization_fragment_with_pinned_sources",
        "missing_work_order_and_activation_lock_zero_write": "test_schedule_gated_supply_rejects_lock_stale_source_and_missing_work_order_without_writes",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-schedule-gated-supply-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-schedule-gated-supply",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-schedule-gated-supply-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["SocialFactAuthority", "OrganizationAuthority"],
        "target_owner": "OrganizationAuthority",
        "stream": "gameplay:organization:{organization_ref}",
        "write_path": "frozen scoped inputs -> PopulationPlanner proposal -> ContinuityMergeAuthority revalidation -> OrganizationAuthority.build_commerce_commitment_fragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only the existing supply fragment is admitted; generic work remains zero-write rejected.",
            "Activation locks remain fail-closed for this direct path; only INF-4C's separately verified released schedule_gated_supply pending row may merge.",
        ],
    }
    path = verification_dir(root) / "infra-schedule-gated-supply-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4A Schedule-Gated Supply Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_schedule_gated_supply_report_json={path}")
    print(f"overall_infra_schedule_gated_supply_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
