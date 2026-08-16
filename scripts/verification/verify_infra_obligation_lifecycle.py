from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    lifecycle_test = root / "backend" / "tests" / "test_infra_obligation_lifecycle.py"
    due_test = root / "backend" / "tests" / "test_infra_multi_domain_obligation.py"
    cases = {
        "registered_settlement_event_derived": (lifecycle_test, "test_registered_construction_settlement_commits_owner_and_lifecycle_events"),
        "clock_due_owner_fragment_event_spine": (due_test, "test_production_due_policy_uses_clock_then_owner_fragment_then_event_spine"),
        "duplicate_idempotency": (due_test, "test_production_due_policy_duplicate_replays_without_second_write"),
        "changed_duplicate_zero_write": (lifecycle_test, "test_registered_settlement_rejects_changed_duplicate_without_append"),
        "cancellation_changed_duplicate_zero_write": (lifecycle_test, "test_registered_cancellation_rejects_changed_duplicate_without_append"),
        "registration_owner_zero_write": (lifecycle_test, "test_registration_owner_mismatch_is_zero_write"),
        "registration_stream_zero_write": (lifecycle_test, "test_registration_stream_mismatch_is_zero_write"),
        "fragment_stream_revision_zero_write": (lifecycle_test, "test_fragment_stream_or_revision_mismatch_is_zero_write"),
        "lifecycle_correlation_zero_write": (lifecycle_test, "test_registered_settlement_requires_lifecycle_correlation_event_without_write"),
        "retry_compensation_unsupported_zero_write": (lifecycle_test, "test_unregistered_and_retry_or_compensation_policy_are_zero_write"),
        "cancellation_event_derived_idempotent": (lifecycle_test, "test_registered_future_cancellation_is_event_derived_and_idempotent"),
        "cancellation_conflict_terminal_zero_write": (lifecycle_test, "test_cancellation_revision_conflict_and_terminal_state_are_zero_write"),
        "cancellation_source_scope_zero_write": (lifecycle_test, "test_cancellation_without_committed_open_source_or_registered_scope_is_zero_write"),
        "cancellation_committed_obligation_identity_zero_write": (lifecycle_test, "test_cancellation_rejects_uncommitted_obligation_id_for_a_committed_run"),
        "cancellation_privacy_scope": (lifecycle_test, "test_cancellation_uses_registered_project_scope_and_filters_public_receipt"),
        "settlement_privacy_full_checkpoint_tail_replay": (lifecycle_test, "test_lifecycle_public_receipt_is_redacted_and_replay_matches"),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-obligation-lifecycle-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-obligation-lifecycle",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(path.relative_to(root)).replace("\\", "/") for path in (lifecycle_test, due_test)],
        "evidence": logs,
        "run_id": f"infra-obligation-lifecycle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/construction_production_runtime.py", "backend/app/world_runtime/obligations.py"],
        "registered_policy": "policy:construction_due_completion@1",
        "stream": "gameplay:construction_production:{facility_ref}",
        "event_types": ["gameplay.construction_production.run_finished", "gameplay.construction_production.obligation_settled", "gameplay.construction_production.obligation_cancelled"],
        "write_path": "caller -> registered construction owner fragment -> GameplayEventStore.append_batch -> project outbox -> replay/scoped receipt",
        "limitations": ["Only construction production policy revision 1 is registered.", "Cancellation derives its identity from the committed construction run-start source; retry, failure, compensation, ecology, and universal lifecycle transitions remain unsupported with zero writes."],
    }
    path = verification_dir(root) / "infra-obligation-lifecycle-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2X Obligation Lifecycle Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_obligation_lifecycle_report_json={path}")
    print(f"overall_infra_obligation_lifecycle_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
