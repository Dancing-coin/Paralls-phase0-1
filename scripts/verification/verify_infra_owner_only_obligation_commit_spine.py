from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests"
    cases = {
        "planner_zero_write": ("test_infra_owner_only_obligation_commit_spine.py", "test_plan_settle_is_zero_write_and_survival_authority_commits_planned_batch"),
        "direct_coordinator_zero_write": ("test_infra_owner_only_obligation_commit_spine.py", "test_direct_coordinator_settle_without_owner_commit_is_zero_write"),
        "raw_store_callback_rejected": ("test_infra_owner_only_obligation_commit_spine.py", "test_coordinator_rejects_store_append_callback_as_non_owner_zero_write"),
        "survival_owner_commit_and_replay": ("test_infra_owner_only_obligation_commit_spine.py", "test_plan_settle_is_zero_write_and_survival_authority_commits_planned_batch"),
        "construction_owner_commit": ("test_infra_construction_maintenance_state_obligation.py", "test_construction_maintenance_state_opens_event_derived_obligation_and_settles_due_expiry"),
        "ecology_owner_commit": ("test_infra_ecology_frost_state_obligation.py", "test_ecology_frost_crop_state_due_expiry_settles_through_existing_coordinator"),
        "economy_wage_owner_commit": ("test_infra_economy_wage_obligation.py", "test_economy_wage_due_is_clock_selected_and_owner_settled"),
        "economy_transfer_owner_commit": ("test_infra_economy_scheduled_transfer_obligation.py", "test_economy_scheduled_transfer_due_settles_account_truth_and_obligation_in_one_batch"),
        "duplicate_idempotency": ("test_infra_economy_scheduled_transfer_obligation.py", "test_economy_scheduled_transfer_open_replays_exact_duplicate_without_second_event"),
        "revision_conflict_zero_write": ("test_infra_economy_scheduled_transfer_obligation.py", "test_economy_scheduled_transfer_due_rejects_stale_revision_without_write"),
        "privacy_scope": ("test_infra_economy_scheduled_transfer_obligation.py", "test_economy_scheduled_transfer_receipt_and_outbox_are_authority_scoped"),
        "checkpoint_tail_replay": ("test_infra_economy_scheduled_transfer_obligation.py", "test_economy_scheduled_transfer_full_and_checkpoint_tail_replay_match"),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    focused_files: set[str] = set()
    for check, (filename, test_name) in cases.items():
        test_path = tests / filename
        log_path = verification_dir(root) / f"infra-owner-only-obligation-commit-spine-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
        focused_files.add(str(test_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-owner-only-obligation-commit-spine",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted(focused_files),
        "evidence": logs,
        "run_id": f"infra-owner-only-obligation-commit-spine-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": [
            "ConstructionProductionAuthority",
            "SurvivalAuthority",
            "EcologyHazardAuthority",
            "EconomyAuthority",
            "EconomyAuthorityService",
        ],
        "write_path": "existing authority -> owner-built obligation batch -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "The coordinator plans and reads append-derived receipts only; it never selects an owner or commits a batch.",
            "This retires one ownership defect in fixed lifecycle rows. It does not admit caller-open policy registration, arbitrary cross-domain settlement, a second scheduler, or a new truth owner.",
        ],
    }
    path = verification_dir(root) / "infra-owner-only-obligation-commit-spine-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2Q Owner-Only Obligation Commit Spine Report",
        {"results": [{"id": name, "status": "proved" if passed else "missing", "title": name} for name, passed in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_owner_only_obligation_commit_spine_report_json={path}")
    print(f"overall_infra_owner_only_obligation_commit_spine_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
