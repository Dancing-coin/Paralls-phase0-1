from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_economy_tax_payment_owner_admission.py"
    selectors = {
        "tax_due_source_pins": "test_tax_due_and_opened_obligation_should_expose_jurisdiction_currency_and_source_revision_pins",
        "economy_payer_binding_pins": "test_tax_obligation_open_should_expose_explicit_economy_payer_binding_pins",
        "atomic_payment_vector": "test_tax_payment_minimal_intent_and_atomic_settlement_vector",
        "atomic_compensation_reopen_and_replay": "test_tax_payment_compensation_atomically_reopens_obligation_and_replays",
        "treasury_identity_privacy_replay_zero_write": "test_treasury_collector_identity_is_private_replayable_and_identity_only",
        "capability_and_collector_zero_write": "test_tax_payment_rejects_capability_or_missing_collector_without_writes",
        "duplicate_receipt_privacy_zero_write": "test_tax_payment_duplicate_receipt_privacy_and_changed_duplicate_are_zero_write",
        "treasury_revision_zero_write": "test_tax_payment_rejects_a_stale_collector_stream_revision_without_writes",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log_path = verification_dir(root) / f"infra-economy-government-tax-payment-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-government-tax-payment",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-economy-government-tax-payment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "treasury_owner_ref": "actor_gameplay.government_treasury_collector",
            "treasury_stream": "gameplay:government_treasury:{jurisdiction_ref}",
            "treasury_event": "gameplay.government_treasury.collector_account_admitted",
            "economy_owner_ref": "actor_gameplay.economy_domain",
            "economy_stream": "gameplay:economy",
            "economy_events": [
                "gameplay.economy.account_debited",
                "gameplay.economy.account_credited",
                "gameplay.economy.tax_payment_settled",
                "gameplay.economy.tax_obligation_settled",
                "gameplay.economy.tax_payment_compensated",
                "gameplay.economy.tax_obligation_reopened",
            ],
            "projection_scope": "authority_only",
        },
        "write_path": "TaxPaymentIntentV1 -> EconomyAuthorityService -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch",
        "limitations": [
            "Treasury owns only the canonical collector-account identity and never writes payer, ledger, payment, or obligation facts.",
            "Economy remains the only payment and compensation writer; this does not admit generic treasury, payment, transfer, or settlement behavior.",
        ],
    }
    path = verification_dir(root) / "infra-economy-government-tax-payment-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2AB Government Tax Payment Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_economy_government_tax_payment_report_json={path}")
    print(f"overall_infra_economy_government_tax_payment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
