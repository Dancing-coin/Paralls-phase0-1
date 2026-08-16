from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_household_org_source_projection.py"
    cases = {
        "social_household_owner_projection": "test_social_authority_records_scoped_household_membership_and_reads_it",
        "organization_schedule_owner_projection": "test_organization_authority_records_schedule_and_rejects_other_recipient",
        "source_revision_reader_validation": "test_source_views_reject_stale_revision_without_writes",
        "owner_provenance_freeze": "test_population_inputs_freeze_owner_provenance_and_revision_vectors",
        "planner_vectors_duplicate": "test_population_planner_pins_both_owner_vectors_and_merge_rechecks_them",
        "scope_zero_write": "test_population_source_input_scope_and_stale_rejection_are_zero_write",
        "forged_provenance_zero_write": "test_population_planner_rejects_forged_source_provenance_and_digest_without_writes",
        "window_privacy_zero_write": "test_organization_schedule_hides_summary_details_and_inactive_windows",
        "full_checkpoint_tail_replay": "test_household_and_organization_source_replay_matches_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-household-org-source-projection-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-household-org-source-projection",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-household-org-source-projection-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["authority:p5:social", "actor_gameplay.organization_domain"],
        "streams": ["gameplay:relationship:{sha256}", "gameplay:organization:{organization_ref}"],
        "event_types": [
            "gameplay.social.household_membership_recorded",
            "gameplay.organization.membership_recorded",
            "gameplay.organization.role_term_recorded",
            "gameplay.organization.shift_offer_recorded",
            "gameplay.organization.work_order_recorded",
        ],
        "write_path": "existing owner -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped reader",
        "limitations": [
            "Household membership is the only admitted household fact; kinship, care, budget, inventory and inheritance remain unsupported.",
            "Organization schedule rows are source projections only; planner emits existing owner intents and cannot mutate organization truth.",
            "Civilization capability input and INF-4Z/INF-4Y consumer binding remain blocked.",
        ],
    }
    path = verification_dir(root) / "infra-household-org-source-projection-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4X Household And Organization Source Projection Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_household_org_source_projection_report_json={path}")
    print(f"overall_infra_household_org_source_projection_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
