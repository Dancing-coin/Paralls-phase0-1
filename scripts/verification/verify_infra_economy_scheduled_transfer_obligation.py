from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_economy_scheduled_transfer_obligation.py"
    cases = {
        "due_settlement_account_and_lifecycle": "test_economy_scheduled_transfer_due_settles_account_truth_and_obligation_in_one_batch",
        "cancellation_terminal_zero_transfer": "test_economy_scheduled_transfer_cancellation_is_terminal_without_moving_account_truth",
        "expiry_terminal_zero_transfer": "test_economy_scheduled_transfer_expiry_is_terminal_without_moving_account_truth",
        "exact_open_duplicate_idempotency": "test_economy_scheduled_transfer_open_replays_exact_duplicate_without_second_event",
        "changed_open_duplicate_zero_write": "test_economy_scheduled_transfer_open_rejects_changed_duplicate_without_write",
        "duplicate_transfer_source_zero_write": "test_economy_scheduled_transfer_open_rejects_duplicate_transfer_source_without_write",
        "stale_revision_zero_write": "test_economy_scheduled_transfer_due_rejects_stale_revision_without_write",
        "due_time_insufficient_funds_zero_write": "test_economy_scheduled_transfer_due_rejects_due_time_insufficient_funds_without_write",
        "forged_owner_fragment_zero_write": "test_economy_scheduled_transfer_due_rejects_forged_owner_fragment_without_write",
        "forged_fragment_revision_zero_write": "test_economy_scheduled_transfer_due_rejects_forged_fragment_revision_without_write",
        "forged_due_identity_zero_write": "test_economy_scheduled_transfer_due_rejects_forged_due_identity_without_write",
        "authority_receipt_and_outbox_privacy": "test_economy_scheduled_transfer_receipt_and_outbox_are_authority_scoped",
        "full_checkpoint_tail_replay": "test_economy_scheduled_transfer_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-economy-scheduled-transfer-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-scheduled-transfer-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-economy-scheduled-transfer-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "actor_gameplay.economy_domain",
        "stream": "gameplay:economy",
        "event_family": [
            "scheduled_transfer_obligation_opened",
            "account_debited",
            "account_credited",
            "scheduled_transfer_obligation_settled",
            "scheduled_transfer_obligation_cancelled",
            "scheduled_transfer_obligation_expired",
        ],
        "write_path": "EconomyAuthorityService -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> authority-only outbox/replay -> EconomyProjector and ObligationLifecycleProjection",
        "limitations": [
            "Only policy:economy_scheduled_account_transfer@1 is registered; callers cannot register policies or submit fragments.",
            "The payment remains a same-stream, same-currency Economy transfer and is not arbitrary cross-domain business settlement.",
            "Retry, compensation, reservation release, and promotion have no approved Economy owner event contract in this package and remain unsupported."
        ],
    }
    path = verification_dir(root) / "infra-economy-scheduled-transfer-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2J Economy Scheduled Transfer Obligation Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_economy_scheduled_transfer_obligation_report_json={path}")
    print(f"overall_infra_economy_scheduled_transfer_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
