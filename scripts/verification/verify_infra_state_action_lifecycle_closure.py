from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    lifecycle_tests = root / "backend" / "tests" / "test_semantic_effect_lifecycle.py"
    action_tests = root / "backend" / "tests" / "test_infra_semantic_survival_state_action.py"
    cases = {
        "pure_dispel_decision": (lifecycle_tests, "test_state_lifecycle_decides_dispel_without_writing"),
        "pure_transform_decision": (lifecycle_tests, "test_state_lifecycle_decides_fixed_transform_without_writing"),
        "dispel_policy_rejection_zero_write": (lifecycle_tests, "test_state_lifecycle_rejects_disallowed_dispel_without_writing"),
        "transform_target_rejection_zero_write": (lifecycle_tests, "test_state_lifecycle_rejects_unregistered_transform_without_writing"),
        "closed_contract_target": (action_tests, "test_registered_survival_action_contract_declares_fixed_recovery_target"),
        "contract_before_fragment_zero_write": (action_tests, "test_semantic_survival_action_uses_the_closed_contract_before_owner_fragment_write"),
        "dispel_owner_settlement": (action_tests, "test_semantic_survival_state_dispel_commits_existing_owner_events"),
        "transform_owner_settlement": (action_tests, "test_semantic_survival_state_transform_commits_fixed_recovery_owner_events"),
        "exact_duplicate_idempotency": (action_tests, "test_semantic_survival_state_action_replays_exact_duplicate_without_write"),
        "changed_duplicate_zero_write": (action_tests, "test_semantic_survival_state_action_rejects_changed_duplicate_without_write"),
        "revision_conflict_zero_write": (action_tests, "test_semantic_survival_state_action_rejects_revision_conflict_without_write"),
        "privacy_scope_zero_write": (action_tests, "test_semantic_survival_state_action_rejects_private_scope_without_write"),
        "full_checkpoint_tail_replay": (action_tests, "test_semantic_survival_state_action_replays_full_and_checkpoint_tail"),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-state-action-lifecycle-closure-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-state-action-lifecycle-closure",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(lifecycle_tests.relative_to(root)).replace("\\", "/"),
            str(action_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": logs,
        "run_id": f"infra-state-action-lifecycle-closure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_rows": [
            {
                "state_refs": ["state:cold", "state:overheated", "state:dehydrated"],
                "owner_ref": "actor_gameplay.survival_domain",
                "stream_pattern": "gameplay:survival:{actor_ref}",
                "action_effects": ["effect:state_dispel", "effect:state_transform_recovery"],
                "transform_targets": ["state:recovering"],
                "projection_scope": "project",
            }
        ],
        "write_path": "semantic proposal -> pure StateDefinition action decision -> existing SurvivalAuthority fragment -> ObligationSettlementCoordinator SettlementPlan -> one GameplayEventStore.append_batch -> project outbox/replay/scoped projection",
        "limitations": [
            "Only the three closed Survival source states and state:recovering transform target are admitted.",
            "This is not a generic action registry, state writer, arbitrary transform language, scheduler, or additional owner matrix row.",
        ],
    }
    path = verification_dir(root) / "infra-state-action-lifecycle-closure-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1O State Action Lifecycle Closure Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_state_action_lifecycle_closure_report_json={path}")
    print(f"overall_infra_state_action_lifecycle_closure_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
