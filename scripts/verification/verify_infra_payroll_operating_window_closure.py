from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_payroll_operating_window_closure.py"
    cases = {
        "success_owner_split_paid_path": "test_payroll_window_closure_success_uses_organization_window_owner_and_economy_payment",
        "invalid_unverified_evidence_zero_write": "test_payroll_window_closure_invalid_or_unverified_evidence_is_zero_write",
        "wage_formal_single_stream_outbox": "test_payroll_wage_accrual_and_overdue_use_formal_settlement_plan_and_actor_outbox",
        "wage_paid_command_plan": "test_payroll_wage_payment_materializes_command_settlement_plan",
        "wage_paid_scoped_outbox": "test_payroll_wage_payment_emits_scoped_actor_and_authority_outbox",
        "compatibility_wrapper_owner_delegate": "test_payroll_window_closure_compatibility_wrapper_delegates_to_organization_owner",
        "duplicate_idempotency": "test_payroll_window_closure_duplicate_idempotency_replays_without_second_write",
        "open_changed_key_revision_conflict": "test_payroll_window_open_changed_idempotency_key_reuse_is_revision_conflict",
        "close_changed_key_revision_conflict": "test_payroll_window_close_changed_idempotency_key_reuse_is_revision_conflict",
        "due_changed_key_revision_conflict": "test_payroll_window_due_changed_idempotency_key_reuse_is_revision_conflict",
        "changed_window_idempotency_zero_write": "test_payroll_window_closure_changed_window_idempotency_key_is_zero_write",
        "stale_revision_zero_write": "test_payroll_window_closure_stale_revision_is_zero_write",
        "privacy_scope_boundary": "test_payroll_window_closure_privacy_scope_and_schedule_views_are_bounded",
        "overdue_terminal_path": "test_payroll_window_closure_explicit_close_can_end_in_overdue",
        "append_derived_receipt": "test_payroll_settlement_receipt_is_append_derived_and_authority_scoped",
        "full_checkpoint_tail_replay": "test_payroll_window_closure_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in cases.items():
        log_path = verification_dir(root) / f"infra-payroll-operating-window-closure-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    report = {
        "profile": "infra-payroll-operating-window-closure",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-payroll-operating-window-closure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "organization_owner": "actor_gameplay.organization_domain",
        "organization_stream": "gameplay:organization:window:{window_ref}",
        "economy_owner": "actor_gameplay.econ1_economy_domain",
        "economy_streams": ["gameplay:economy:wage:{worker_ref}", "gameplay:economy"],
        "write_path": "Organization window and Economy wage/account writes each use GameplayCommandEnvelope/SettlementPlan or existing owner fragments into one GameplayEventStore.append_batch() result; payroll receipts are derived read-only from that append result",
        "limitations": [
            "This package does not admit a scheduler, a new obligation store, generic payroll policy, or arbitrary cross-domain settlement.",
            "Economy compatibility window helpers delegate to OrganizationAuthority only and do not retain a second writer.",
            "The receipt helper is authority-scoped and append-derived; it is not a receipt store or a second settlement writer.",
        ],
    }
    path = verification_dir(root) / "infra-payroll-operating-window-closure-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2P Payroll And Organization Operating-Window Closure Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_payroll_operating_window_closure_report_json={path}")
    print(f"overall_infra_payroll_operating_window_closure_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
