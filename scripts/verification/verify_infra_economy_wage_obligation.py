from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_economy_wage_obligation.py"
    cases = {
        "owner_open_event_and_lifecycle_projection": "test_economy_wage_obligation_opens_on_existing_owner_stream",
        "caller_due_and_owner_settlement_receipt": "test_economy_wage_due_is_clock_selected_and_owner_settled",
        "duplicate_and_changed_duplicate": "test_economy_wage_open_duplicate_and_changed_duplicate_are_distinct",
        "reopened_identity_zero_write": "test_economy_wage_rejects_reopened_obligation_identity_without_writes",
        "revision_privacy_terminal_zero_write": "test_economy_wage_rejects_stale_scope_and_terminal_without_writes",
        "settlement_revision_zero_write": "test_economy_wage_settlement_rejects_changed_owner_stream_revision_without_write",
        "outbox_privacy_and_checkpoint_tail_replay": "test_economy_wage_checkpoint_tail_replay_and_project_outbox_are_scoped",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-economy-wage-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-wage-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-economy-wage-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "actor_gameplay.econ1_economy_domain / EconomyAuthority",
        "stream": "gameplay:economy:wage:{worker_ref}",
        "write_path": "EconomyAuthority -> GameplayCommandEnvelope/SettlementPlan or OwnerAuthorizedFragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "enabled_lifecycle": ["open", "due", "settled"],
        "limitations": ["No Economy cancellation, retry, compensation, payment, account transfer, generic work, activation binding, or cross-stream atomic receipt is admitted."],
    }
    path = verification_dir(root) / "infra-economy-wage-obligation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2C Economy Wage Obligation Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_economy_wage_obligation_report_json={path}")
    print(f"overall_infra_economy_wage_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
