from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    test_path = root / "backend" / "tests" / "test_simulation_clock.py"
    python = resolve_python_exe(None)
    checks = {}
    logs = []
    for name in ("test_clock_is_explicit_and_budgeted", "test_clock_filters_closed_and_rejects_rewind"):
        log_path = verification_dir(root) / f"infra-time-obligation-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", name], root, log_path)
        checks[name] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    obligation_test_path = root / "backend" / "tests" / "test_infra_time_obligation.py"
    economy_test_path = root / "backend" / "tests" / "test_infra_economy_wage_obligation.py"
    production_test_path = root / "backend" / "tests" / "test_infra_multi_domain_obligation.py"
    obligation_cases = {
        "caller_driven_lifecycle_and_receipt": (economy_test_path, "test_economy_wage_due_is_clock_selected_and_owner_settled"),
        "duplicate_idempotency": (production_test_path, "test_production_due_policy_duplicate_replays_without_second_write"),
        "revision_conflict_zero_write": (obligation_test_path, "test_obligation_revision_conflict_is_zero_write"),
        "closed_and_unauthorized_zero_write": (obligation_test_path, "test_closed_or_unauthorized_fragment_is_zero_write"),
        "privacy_and_checkpoint_tail_replay": (obligation_test_path, "test_obligation_full_and_checkpoint_tail_replay_match_and_scope_is_filtered"),
        "economy_owner_due_fragment": (obligation_test_path, "test_economy_due_fragment_settles_only_through_coordinator"),
        "survival_owner_due_fragment": (obligation_test_path, "test_survival_due_fragment_rejects_bad_mode_without_writing"),
        "production_owner_due_fragment": (obligation_test_path, "test_production_due_fragment_checks_finish_before_coordinator_write"),
    }
    for name, (case_path, test_name) in obligation_cases.items():
        log_path = verification_dir(root) / f"infra-time-obligation-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(case_path), "-k", test_name], root, log_path)
        checks[name] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    activation_test_path = root / "backend" / "tests" / "test_population_continuity.py"
    activation_cases = {
        "legacy_activation_deferral_fixture": "test_activation_lock_records_replayable_schedule_pending_then_releases",
        "activation_lock_revision_zero_write": "test_activation_lock_stale_pending_or_release_is_zero_write",
    }
    for name, test_name in activation_cases.items():
        log_path = verification_dir(root) / f"infra-time-obligation-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(activation_test_path), "-k", test_name], root, log_path)
        checks[name] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-time-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(test_path.relative_to(root)).replace("\\", "/"),
            str(obligation_test_path.relative_to(root)).replace("\\", "/"),
            str(economy_test_path.relative_to(root)).replace("\\", "/"),
            str(production_test_path.relative_to(root)).replace("\\", "/"),
            str(activation_test_path.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": logs,
        "run_id": f"infra-time-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/world_runtime/simulation_clock.py", "backend/app/world_runtime/obligations.py", "backend/app/population_continuity/activation.py"],
        "write_path": "caller -> due selection -> owner-authorized fragments -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "no_background_loop": True,
        "limitations": [
            "This historical profile proves explicit clock/coordinator behavior and named owner-fragment fixtures, not a completed economy/survival/production lifecycle matrix.",
            "Its activation fixture is not event-derived ScheduledObligation integration; only INF-4C's named released schedule_gated_supply row has that separate evidence.",
        ],
    }
    path = verification_dir(root) / "infra-time-obligation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2 Time Obligation Report", {"results": [{"id": k, "status": "proved" if v else "missing", "title": k} for k, v in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_time_obligation_report_json={path}")
    print(f"overall_infra_time_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
