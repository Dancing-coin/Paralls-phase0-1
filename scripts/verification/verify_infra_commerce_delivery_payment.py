from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_commerce_delivery_payment.py"
    cases = {
        "payment_single_append_receipt": "test_commerce_delivery_payment_uses_committed_sources_and_one_economy_append",
        "source_owner_currency_privacy_revision_zero_write": "test_commerce_delivery_payment_rejects_forged_source_account_currency_privacy_and_revision_without_write",
        "reservation_and_source_revision_or_head_zero_write": "test_commerce_delivery_payment_rejects_uncommitted_reservation_and_source_revision_or_head_mismatch_without_write",
        "duplicate_idempotency": "test_commerce_delivery_payment_replays_exact_duplicate_and_rejects_changed_duplicate",
        "compensation_closed_reversal": "test_commerce_delivery_payment_compensation_reverses_exact_accounts_and_rejects_duplicate_without_write",
        "compensation_insufficient_funds_zero_write": "test_commerce_delivery_payment_compensation_rejects_insufficient_seller_funds_without_write",
        "authority_privacy_checkpoint_tail_replay": "test_commerce_delivery_payment_scope_and_checkpoint_tail_replay_are_authority_only",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-commerce-delivery-payment-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[name] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-commerce-delivery-payment",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-commerce-delivery-payment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "actor_gameplay.economy_domain",
        "stream": "gameplay:economy",
        "event_family": [
            "gameplay.economy.account_debited",
            "gameplay.economy.account_credited",
            "gameplay.economy.commerce_delivery_payment_settled",
            "gameplay.economy.commerce_delivery_payment_compensated",
        ],
        "write_path": "EconomyAuthorityService -> GameplayCommandEnvelope/SettlementPlan -> one GameplayEventStore.append_batch -> authority-only outbox/replay/scoped projection",
        "limitations": [
            "Only committed delivery evidence and its committed Economy obligation/reservation vector are admitted.",
            "This is not caller-open policy registration, arbitrary payment routing, generic compensation, or generic cross-domain settlement.",
        ],
    }
    report_path = verification_dir(root) / "infra-commerce-delivery-payment-report.json"
    write_json(report_path, report)
    write_markdown(
        report_path.with_suffix(".md"),
        "INF-2AA Commerce Delivery Payment Report",
        {"results": [{"id": name, "status": "proved" if value else "missing", "title": name} for name, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_commerce_delivery_payment_report_json={report_path}")
    print(f"overall_infra_commerce_delivery_payment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
