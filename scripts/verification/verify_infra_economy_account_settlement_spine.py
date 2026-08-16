from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_economy_account_settlement_spine.py"
    cases = {
        "formal_owner_command_plan_append": "test_account_transfer_uses_formal_command_envelope_settlement_plan_and_one_append_batch",
        "authority_scoped_redacted_outbox": "test_account_transfer_outbox_is_authority_scoped_and_redacted",
        "budget_reservation_formal_spine": "test_budget_reservation_uses_formal_spine_and_redacted_authority_outbox",
        "append_derived_authority_receipt": "test_account_transfer_receipt_is_derived_from_the_append_result",
        "duplicate_idempotency": "test_account_transfer_duplicate_replays_without_double_debit",
        "changed_duplicate_zero_write": "test_account_transfer_changed_duplicate_is_zero_write",
        "stale_revision_zero_write": "test_stale_account_revision_is_zero_write",
        "insufficient_funds_zero_write": "test_insufficient_account_funds_are_zero_write",
        "full_checkpoint_tail_replay": "test_account_projection_full_and_checkpoint_tail_replay_match",
        "account_projection_privacy": "test_account_projection_is_visible_only_to_owner_or_authority",
        "receipt_privacy_zero_write": "test_account_receipt_rejects_non_authority_scope_without_writes",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-economy-account-settlement-spine-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-account-settlement-spine",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-economy-account-settlement-spine-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "actor_gameplay.economy_domain",
        "stream": "gameplay:economy",
        "event_family": ["account_opened", "account_debited", "account_credited", "budget_reserved"],
        "write_path": "EconomyAuthorityService -> GameplayCommandEnvelope -> SettlementPlan -> one GameplayEventStore.append_batch -> authority-scoped outbox -> EconomyProjector/EconomyPrivacyQueryService",
        "limitations": [
            "This admits only existing account opening, same-stream transfer and budget reservation writes.",
            "It does not create open policy registration, payment obligations, generic payment, or arbitrary cross-domain atomic settlement.",
            "EconomyAuthority wage lifecycle remains a separate principal and contract."
        ],
    }
    path = verification_dir(root) / "infra-economy-account-settlement-spine-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2H Economy Account Settlement Spine Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_economy_account_settlement_spine_report_json={path}")
    print(f"overall_infra_economy_account_settlement_spine_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
