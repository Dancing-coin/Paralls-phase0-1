from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_government_branch_scenario.py"
    cases = {
        "government_owner_scenario_append": "test_accepted_inspection_branch_proposal_settles_on_government_scenario_stream",
        "duplicate_idempotency": "test_government_branch_scenario_duplicate_idempotency_replays_without_second_append",
        "duplicate_retry_after_source_advance": "test_government_branch_scenario_duplicate_retry_replays_after_production_source_advances",
        "changed_duplicate_zero_write": "test_government_branch_scenario_changed_duplicate_rejects_without_append",
        "privacy_zero_write": "test_government_branch_scenario_rejects_privacy_without_append",
        "unknown_candidate_zero_write": "test_government_branch_scenario_rejects_unknown_candidate_without_append",
        "failed_inspection_zero_write": "test_government_branch_scenario_rejects_failed_inspection_without_append",
        "revision_conflict_zero_write": "test_government_branch_scenario_rejects_stale_revision_without_append",
        "checkpoint_tail_replay": "test_government_branch_scenario_checkpoint_tail_replay_matches_full",
        "production_replay_isolation": "test_government_branch_scenario_does_not_change_production_replay",
        "promotion_unsupported": "test_government_branch_scenario_promotion_remains_unsupported",
        "scoped_outbox": "test_government_branch_scenario_emits_only_scoped_scenario_outbox",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-government-branch-scenario-settlement-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-government-branch-scenario-settlement",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-government-branch-scenario-settlement-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "GovernmentAuthority",
        "stream": "gameplay:government_branch:{branch_ref}:{organization_ref}",
        "event": "gameplay.government.branch_inspection_recorded",
        "write_path": "BranchPreviewAuthority proposal -> GovernmentAuthority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> scoped outbox -> scenario replay projection",
        "limitations": [
            "Only an accepted inspection candidate with passed=True can create one Government scenario event.",
            "Failed inspection remains zero-write because a branch remediation-obligation lifecycle is not admitted.",
            "Scenario streams are excluded from production replay and are not production government truth.",
            "Generic branch settlement, cross-domain receipts and promotion remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-government-branch-scenario-settlement-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4I Government Branch Scenario Settlement Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_government_branch_scenario_settlement_report_json={path}")
    print(f"overall_infra_government_branch_scenario_settlement_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
