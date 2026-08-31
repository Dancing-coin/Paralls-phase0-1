from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_economy_wage_terminal_lifecycle.py"
    cases = {
        "authority_owned_closed_registration": "test_economy_wage_registration_is_authority_owned_and_closed",
        "retry_owner_fragment": "test_economy_wage_retry_is_owner_fragment_event_derived",
        "cancel_owner_fragment": "test_economy_wage_cancel_is_owner_fragment_event_derived",
        "expiry_owner_fragment_and_receipt": "test_economy_wage_expiry_plan_is_zero_write_and_owner_commit_is_append_derived",
        "expiry_idempotency_revision_terminal_zero_write": "test_economy_wage_expiry_is_idempotent_and_rejects_stale_or_terminal_without_writes",
        "expiry_privacy_checkpoint_tail_replay": "test_economy_wage_expiry_is_project_scoped_and_checkpoint_tail_replayable",
        "retry_idempotency_revision_zero_write": "test_economy_wage_retry_is_idempotent_and_stale_retry_is_zero_write",
        "retry_changed_duplicate_zero_write": "test_economy_wage_retry_rejects_changed_duplicate_without_append",
        "expiry_changed_duplicate_zero_write": "test_economy_wage_expiry_rejects_changed_duplicate_without_append",
        "settled_only_compensation_replay": "test_economy_wage_compensation_is_settled_only_and_replayable",
        "compensation_changed_duplicate_zero_write": "test_economy_wage_compensation_rejects_changed_duplicate_without_append",
        "terminal_zero_write": "test_economy_wage_terminal_cancel_and_unsettled_compensation_are_zero_write",
    }
    checks: dict[str, bool] = {}; logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-economy-wage-terminal-lifecycle-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0; logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-wage-terminal-lifecycle", "overall_passed": all(checks.values()),
        "checks": checks, "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs, "run_id": f"infra-economy-wage-terminal-lifecycle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root), "owner": "actor_gameplay.econ1_economy_domain",
        "stream": "gameplay:economy:wage:{worker_ref}",
        "event_family": ["wage_obligation_opened", "wage_obligation_retry_scheduled", "wage_obligation_cancelled", "wage_obligation_expired", "wage_obligation_settled", "wage_obligation_compensated"],
        "write_path": "EconomyAuthority owner fragment -> ObligationSettlementCoordinator assembly -> one GameplayEventStore.append_batch -> outbox/replay",
        "limitations": ["Expiry only closes an unpaid wage obligation and writes no wage accrual, payment, or account change.", "Compensation reverses only wage accrual semantics; no payment/account transfer.", "No generic cross-domain receipt, activation binding, or other owner lifecycle is admitted."],
    }
    path = verification_dir(root) / "infra-economy-wage-terminal-lifecycle-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2D Economy Wage Terminal Lifecycle Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_economy_wage_terminal_lifecycle_report_json={path}")
    print(f"overall_infra_economy_wage_terminal_lifecycle_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
