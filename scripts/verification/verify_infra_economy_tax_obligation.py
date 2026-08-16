from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_file = root / "backend" / "tests" / "test_infra_economy_tax_obligation.py"
    cases = {
        "source_pinned_open": "test_tax_obligation_open_is_pinned_to_committed_tax_due_event",
        "idempotency_and_changed_duplicate": "test_tax_obligation_open_replays_exact_duplicate_and_rejects_changed_duplicate",
        "forged_source_and_revision_zero_write": "test_tax_obligation_open_rejects_forged_source_and_stale_revision_without_write",
        "catalog_gate_zero_write": "test_tax_obligation_catalog_gate_rejects_before_append",
        "terminal_settlement_no_account_mutation": "test_tax_obligation_settlement_is_terminal_only_and_replayable",
        "terminal_cancel_expire": "test_tax_obligation_cancel_and_expire_are_owner_terminal_events",
        "authority_only_privacy": "test_tax_obligation_privacy_redacts_amount_and_evidence_from_outbox",
        "full_checkpoint_tail_replay": "test_tax_obligation_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, selector in cases.items():
        log = verification_dir(root) / f"infra-economy-tax-obligation-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_file), "-k", selector], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-economy-tax-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_file.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-economy-tax-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "EconomyAuthorityService -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> Economy scoped outbox/replay",
        "limitations": [
            "Tax obligation is one fixed existing Economy owner row; caller-open policy registration remains rejected.",
            "Settlement records terminal obligation state only and never debits or credits an account.",
            "No generic cross-domain payment or tax collector is admitted by this package.",
        ],
    }
    path = verification_dir(root) / "infra-economy-tax-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2Z Economy Tax Obligation Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()]},
        "overall_passed",
    )
    print(f"infra_economy_tax_obligation_report_json={path}")
    print(f"overall_infra_economy_tax_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
