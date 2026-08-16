from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_survival_state_obligation.py"
    cases = {
        "formal_owner_matrix_and_unmapped_scheduled_rejection": "test_survival_state_expiry_lifecycle_is_the_only_registered_scheduled_owner_row",
        "scheduled_apply_opens_owner_obligation": "test_survival_scheduled_state_application_commits_state_and_open_obligation",
        "due_expiry_uses_single_clock_and_coordinator": "test_due_survival_state_expiry_is_selected_by_clock_and_settled_by_existing_coordinator",
        "add_stack_policy": "test_survival_state_add_policy_increments_stacks",
        "replace_stack_policy": "test_survival_state_replace_policy_resets_stacks",
        "refresh_stack_policy": "test_survival_state_refresh_policy_retains_stacks",
        "reject_stack_policy_zero_write": "test_survival_state_reject_policy_is_zero_write_at_limit",
        "duplicate_revision_forged_owner_zero_write": "test_survival_state_duplicate_revision_and_forged_owner_are_zero_write",
        "dispel_cancels_committed_open_obligation": "test_survival_state_dispel_cancels_only_committed_open_obligation",
        "transform_cancellation_and_checkpoint_tail_replay": "test_survival_state_transform_cancels_prior_expiry_and_rebuilds_from_checkpoint_tail",
        "scoped_projection_privacy": "test_survival_state_public_projection_redacts_effect_and_obligation_details",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        target = root / "backend" / "tests" / "test_infra_general_semantic_rule.py" if check.startswith("formal_") else test_path
        log_path = verification_dir(root) / f"infra-survival-state-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(target), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-survival-state-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-survival-state-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/survival_runtime.py", "backend/app/world_runtime/obligations.py"],
        "registered_policy": "policy:survival_state_expiry@1",
        "stream": "gameplay:survival:{actor_ref}",
        "event_types": [
            "gameplay.survival.state_applied",
            "gameplay.survival.obligation_opened",
            "gameplay.survival.state_expired",
            "gameplay.survival.obligation_settled",
            "gameplay.survival.state_dispelled",
            "gameplay.survival.state_transformed",
            "gameplay.survival.obligation_cancelled",
        ],
        "write_path": "SurvivalAuthority -> GameplayCommandEnvelope / owner fragment -> GameplayEventStore.append_batch -> project outbox -> scoped projection/replay",
        "limitations": [
            "This proves one Survival-owned cold state-expiry row, not generic semantic state ownership.",
            "The pure evaluator is proposal-only; closed semantic bridges may only hand the registered cold/heat proposals to Survival, which remains the sole writer.",
            "Retry, compensation, periodic state effects, ecology propagation, and additional owner rows remain unimplemented.",
        ],
    }
    path = verification_dir(root) / "infra-survival-state-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1A Survival State Obligation Report",
        {"results": [{"id": name, "status": "proved" if passed else "missing", "title": name} for name, passed in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_survival_state_obligation_report_json={path}")
    print(f"overall_infra_survival_state_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
