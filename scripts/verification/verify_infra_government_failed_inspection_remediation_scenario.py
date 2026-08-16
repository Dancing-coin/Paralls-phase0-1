from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_government_failed_inspection_remediation_scenario.py"
    predecessor_script = root / "scripts" / "verification" / "verify_infra_government_branch_scenario_settlement.py"
    cases = {
        "government_owner_scenario_append": "test_failed_inspection_settles_fixed_government_remediation_on_scenario_stream",
        "forged_provenance_zero_write": "test_direct_forged_government_remediation_submission_is_zero_write",
        "derived_fixed_remediation_identity": "test_failed_inspection_remediation_derives_fixed_identity_and_action",
        "duplicate_idempotency": "test_failed_inspection_remediation_duplicate_replays_without_second_append",
        "changed_duplicate_zero_write": "test_failed_inspection_remediation_rejects_changed_duplicate_without_append",
        "privacy_zero_write": "test_failed_inspection_remediation_rejects_public_scope_without_append",
        "unknown_candidate_zero_write": "test_failed_inspection_remediation_rejects_unknown_candidate_without_append",
        "passed_candidate_zero_write": "test_failed_inspection_remediation_rejects_passed_candidate_without_append",
        "scenario_revision_zero_write": "test_failed_inspection_remediation_rejects_stale_scenario_revision_without_append",
        "government_source_revision_zero_write": "test_failed_inspection_remediation_rejects_stale_government_source_without_append",
        "scoped_outbox": "test_failed_inspection_remediation_outbox_is_creator_debug_scoped",
        "checkpoint_tail_replay": "test_failed_inspection_remediation_projection_replays_checkpoint_tail",
        "production_replay_and_promotion_zero_write": "test_failed_inspection_remediation_keeps_production_replay_and_promotion_zero_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    predecessor_log = verification_dir(root) / "infra-government-failed-inspection-remediation-scenario-predecessor-inf4i.log"
    predecessor = run_command([python, str(predecessor_script)], root, predecessor_log)
    checks["predecessor_inf4i"] = predecessor.returncode == 0
    evidence.append(str(predecessor_log.relative_to(root)).replace("\\", "/"))
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-government-failed-inspection-remediation-scenario-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-government-failed-inspection-remediation-scenario",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-government-failed-inspection-remediation-scenario-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "GovernmentAuthority",
        "stream": "gameplay:government_branch:{branch_ref}:{organization_ref}",
        "event": "gameplay.government.branch_inspection_remediation_recorded",
        "write_path": "BranchPreviewAuthority proposal -> GovernmentAuthority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> scoped outbox -> scenario replay projection",
        "limitations": [
            "Only an accepted inspection candidate with passed=False can create the fixed follow_up_required remediation record.",
            "This is not a ScheduledObligation, remediation scheduler, generic branch receipt, promotion, or production Government truth.",
        ],
    }
    path = verification_dir(root) / "infra-government-failed-inspection-remediation-scenario-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4J Government Failed-Inspection Remediation Scenario Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_government_failed_inspection_remediation_scenario_report_json={path}")
    print(f"overall_infra_government_failed_inspection_remediation_scenario_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
