from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_organization_economy_commerce_commitment.py"
    cases = {
        "owner_fragment_plan_one_append": "test_commitment_uses_one_owner_fragment_append",
        "append_derived_authority_receipt": "test_commitment_receipt_is_derived_from_the_append_result",
        "exact_duplicate_idempotency": "test_exact_duplicate_replays_the_original_append_without_writing",
        "changed_duplicate_zero_write": "test_changed_duplicate_is_rejected_before_stale_revision_checks_without_writing",
        "stale_organization_revision_zero_write": "test_stale_organization_revision_is_zero_write",
        "stale_economy_revision_zero_write": "test_stale_economy_revision_is_zero_write",
        "missing_budget_reservation_zero_write": "test_missing_economy_reservation_is_zero_write",
        "public_projection_privacy": "test_public_projection_redacts_account_private_values",
        "outbox_privacy": "test_commitment_outbox_redacts_account_private_values",
        "full_checkpoint_tail_replay": "test_full_and_checkpoint_tail_replay_match_for_commitment_batch",
        "receipt_scope_zero_write": "test_receipt_scope_rejection_is_zero_write",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-organization-economy-commerce-commitment-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-organization-economy-commerce-commitment",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-organization-economy-commerce-commitment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "assembly_principal": "actor_gameplay.commerce_authority",
        "owners": ["OrganizationAuthority", "EconomyAuthorityService", "InventoryAuthorityService", "Econ1EconomyAuthority (optional wage)"],
        "streams": ["gameplay:organization:{organization_ref}", "gameplay:economy", "gameplay:inventory:{seller_organization_ref}", "gameplay:economy:wage:{worker_ref} (optional)"],
        "event_family": ["gameplay.organization.commerce_commitment_accepted", "gameplay.economy.commerce_obligation_recorded", "existing commerce custody event", "gameplay.economy.wage_accrued (optional)"],
        "write_path": "CommerceAuthority -> GameplayCommandEnvelope / SettlementPlan -> existing owner fragments -> one GameplayEventStore.append_batch -> redacted authority:commerce outbox -> owner scoped projections/replay",
        "limitations": [
            "CommerceAuthority owns no Organization, Economy, Inventory, Contract, or Wage truth and accepts no caller-selected stream/event route.",
            "This is one named commerce commitment settlement, not generic cross-domain settlement, payment, policy registration, a scheduler, or a second receipt/store.",
            "Group simulation and branch promotion remain outside this package."
        ],
    }
    path = verification_dir(root) / "infra-organization-economy-commerce-commitment-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2I Organization/Economy Commerce Commitment Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_organization_economy_commerce_commitment_report_json={path}")
    print(f"overall_infra_organization_economy_commerce_commitment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
