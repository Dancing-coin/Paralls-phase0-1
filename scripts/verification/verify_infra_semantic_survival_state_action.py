from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_semantic_survival_state_action.py"
    cases = {
        "dispel_success": "test_semantic_survival_state_dispel_commits_existing_owner_events",
        "transform_success": "test_semantic_survival_state_transform_commits_fixed_recovery_owner_events",
        "unknown_effect_zero_write": "test_semantic_survival_state_action_rejects_unknown_effect_without_write",
        "unregistered_route_zero_write": "test_semantic_survival_state_action_rejects_unregistered_route_without_write",
        "wrong_owner_zero_write": "test_semantic_survival_state_action_rejects_wrong_owner_without_write",
        "wrong_stream_zero_write": "test_semantic_survival_state_action_rejects_wrong_stream_without_write",
        "private_scope_zero_write": "test_semantic_survival_state_action_rejects_private_scope_without_write",
        "stale_vector_zero_write": "test_semantic_survival_state_action_rejects_stale_vector_without_write",
        "blank_reason_zero_write": "test_semantic_survival_state_action_rejects_blank_reason_without_write",
        "revision_conflict_zero_write": "test_semantic_survival_state_action_rejects_revision_conflict_without_write",
        "changed_duplicate_zero_write": "test_semantic_survival_state_action_rejects_changed_duplicate_without_write",
        "exact_duplicate_idempotency": "test_semantic_survival_state_action_replays_exact_duplicate_without_write",
        "changed_snapshot_duplicate_zero_write": "test_semantic_survival_state_action_rejects_changed_snapshot_duplicate_without_write",
        "project_outbox_scope": "test_semantic_survival_state_action_outbox_is_project_scoped",
        "full_checkpoint_tail_replay": "test_semantic_survival_state_action_replays_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-survival-state-action-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-survival-state-action",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-semantic-survival-state-action-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_rows": [
            {
                "effect_ref": "effect:state_dispel",
                "owner_ref": "actor_gameplay.survival_domain",
                "stream_pattern": "gameplay:survival:{actor_ref}",
                "events": ["gameplay.survival.state_dispelled", "gameplay.survival.obligation_cancelled"],
                "projection_scope": "project",
            },
            {
                "effect_ref": "effect:state_transform_recovery",
                "owner_ref": "actor_gameplay.survival_domain",
                "stream_pattern": "gameplay:survival:{actor_ref}",
                "events": [
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                ],
                "projection_scope": "project",
            },
        ],
        "write_path": "closed semantic state-action route -> existing SurvivalAuthority fragment -> ObligationSettlementCoordinator -> SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": [
            "This proves two closed Survival state-action rows only; it does not admit generic state actions or arbitrary replacement states.",
            "The semantic registry remains closed and MetaRule remains proposal-only.",
        ],
    }
    path = verification_dir(root) / "infra-semantic-survival-state-action-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1K Semantic Survival State Action Lifecycle Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_semantic_survival_state_action_report_json={path}")
    print(f"overall_infra_semantic_survival_state_action_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
