from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_government_inspection_promotion.py"
    selectors = {
        "government_owner_production_append": "test_government_promotes_one_durable_passed_inspection_into_existing_production_stream",
        "exact_duplicate_receipt_replay": "test_government_promotion_exact_duplicate_reconstructs_receipt_without_second_append",
        "changed_duplicate_zero_write": "test_government_promotion_rejects_changed_duplicate_without_append",
        "stale_source_zero_write": "test_government_promotion_rejects_stale_production_source_without_append",
        "privacy_zero_write": "test_government_promotion_rejects_wrong_privacy_without_append",
        "forged_scenario_zero_write": "test_government_promotion_rejects_forged_scenario_identity_without_append",
        "scoped_outbox_and_checkpoint_tail_replay": "test_government_promotion_emits_scoped_outbox_and_replays_production_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log_path = verification_dir(root) / f"infra-government-inspection-promotion-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-government-inspection-promotion",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-government-inspection-promotion-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "GovernmentAuthority",
        "source": "durable branch-preview admission plus Government branch inspection scenario",
        "stream": "gameplay:government:{organization_ref}",
        "event": "gameplay.government.inspection_recorded",
        "write_path": "GovernmentAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> project outbox -> production replay",
        "limitations": [
            "Only one passed Government inspection row with matching durable branch admission and scenario evidence is admitted.",
            "BranchPreviewAuthority remains proposal/evidence-only and cannot write production truth.",
            "Organization, remediation, generic branch promotion and complete group simulation remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-government-inspection-promotion-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4N Government Inspection Promotion Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
