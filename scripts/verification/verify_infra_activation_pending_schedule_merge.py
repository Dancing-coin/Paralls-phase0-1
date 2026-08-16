from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    population_tests = root / "backend" / "tests" / "test_population_continuity.py"
    schedule_tests = root / "backend" / "tests" / "test_infra_household_org_source_projection.py"
    cases = {
        "event_derived_pending_and_release": (population_tests, "test_activation_lock_records_replayable_schedule_pending_then_releases"),
        "unsupported_pending_zero_write": (population_tests, "test_activation_schedule_pending_rejects_free_form_payload_without_writes"),
        "pending_duplicate_idempotency": (population_tests, "test_activation_schedule_pending_duplicate_is_idempotent"),
        "pending_privacy_scope": (population_tests, "test_activation_schedule_pending_privacy_scope_filters_view"),
        "pending_checkpoint_tail_replay": (population_tests, "test_activation_schedule_pending_checkpoint_tail_replay_matches_full"),
        "released_owner_fragment_merge": (schedule_tests, "test_released_activation_pending_schedule_merges_only_through_existing_organization_owner"),
        "forged_or_stale_zero_write": (schedule_tests, "test_activation_pending_schedule_forgery_or_stale_release_is_zero_write_at_organization_boundary"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-activation-pending-schedule-merge-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-activation-pending-schedule-merge",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(population_tests.relative_to(root)).replace("\\", "/"), str(schedule_tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-activation-pending-schedule-merge-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "OrganizationAuthority"],
        "activation_stream": "population:{world_ref}",
        "target_stream": "gameplay:organization:{organization_ref}",
        "write_path": "ProfileActivationAuthority pending/release events -> event-derived pending projection -> ContinuityMergeAuthority revalidation -> OrganizationAuthority fragment -> GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": [
            "Only schedule_gated_supply pending payloads are admitted.",
            "This is not a generic pending queue, obligation coordinator binding, branch promotion, or population truth owner.",
        ],
    }
    path = verification_dir(root) / "infra-activation-pending-schedule-merge-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4C Activation Pending Schedule Merge Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_activation_pending_schedule_merge_report_json={path}")
    print(f"overall_infra_activation_pending_schedule_merge_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
