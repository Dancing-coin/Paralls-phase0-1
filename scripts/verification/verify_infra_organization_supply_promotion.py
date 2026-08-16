from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_organization_supply_promotion.py"
    selectors = {
        "organization_owner_production_append": "test_organization_promotes_one_durable_supply_into_existing_production_stream",
        "exact_duplicate_receipt_replay": "test_organization_supply_promotion_exact_duplicate_reconstructs_receipt_without_second_append",
        "changed_duplicate_zero_write": "test_organization_supply_promotion_rejects_changed_duplicate_without_append",
        "source_revision_conflict_zero_write": "test_organization_supply_promotion_rejects_stale_source_without_append",
        "privacy_zero_write": "test_organization_supply_promotion_rejects_wrong_privacy_without_append",
        "forged_scenario_zero_write": "test_organization_supply_promotion_rejects_forged_source_or_scenario_without_append",
        "forged_admission_zero_write": "test_organization_supply_promotion_rejects_forged_admission_without_append",
        "scoped_outbox_and_checkpoint_tail_replay": "test_organization_supply_promotion_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log_path = verification_dir(root) / f"infra-organization-supply-promotion-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-organization-supply-promotion",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-organization-supply-promotion-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "OrganizationAuthority",
        "source": "durable BranchPreview supply admission plus Organization branch scenario",
        "stream": "gameplay:organization:{organization_ref}",
        "event": "gameplay.organization.commerce_commitment_accepted",
        "write_path": "OrganizationAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> project outbox -> production replay",
        "limitations": [
            "Only one accepted Organization supply row with exact durable admission and scenario identity is admitted.",
            "BranchPreview remains proposal/evidence-only and cannot write production truth.",
            "Generic branch settlement/receipt/promotion, other owner rows and complete group simulation remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-organization-supply-promotion-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4O Organization Supply Promotion Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
