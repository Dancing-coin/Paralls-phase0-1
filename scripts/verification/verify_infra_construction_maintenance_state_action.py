from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    action_tests = root / "backend" / "tests" / "test_infra_construction_maintenance_state_action.py"
    lifecycle_tests = root / "backend" / "tests" / "test_infra_construction_maintenance_state_obligation.py"
    cases = {
        "owner_action_cancellation_batch": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_clears_state_and_cancels_open_obligation_in_one_batch",
        ),
        "exact_duplicate_idempotency": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_replays_exact_duplicate_without_write",
        ),
        "changed_duplicate_zero_write": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_rejects_changed_duplicate_without_write",
        ),
        "revision_conflict_zero_write": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_rejects_revision_conflict_without_write",
        ),
        "privacy_scope_zero_write": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_rejects_nonproject_privacy_without_write",
        ),
        "closed_contract_before_fragment_zero_write": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_uses_closed_state_contract_before_fragment_write",
        ),
        "transform_zero_write": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_rejects_transform_without_write",
        ),
        "unknown_effect_zero_write": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_rejects_unknown_effect_without_write",
        ),
        "full_checkpoint_tail_replay": (
            action_tests,
            "test_semantic_construction_maintenance_dispel_checkpoint_tail_replay_matches_full_projection",
        ),
        "ordinary_cancellation_remains_unsupported": (
            lifecycle_tests,
            "test_construction_maintenance_state_obligation_rejects_cancel_without_write",
        ),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-construction-maintenance-state-action-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-maintenance-state-action",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(action_tests.relative_to(root)).replace("\\", "/"),
            str(lifecycle_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": logs,
        "run_id": f"infra-construction-maintenance-state-action-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "effect_ref": "effect:maintenance_state_dispel",
            "state_ref": "state:maintenance_due",
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "action_event_type": "gameplay.construction_production.maintenance_state_dispelled",
            "cancelled_event_type": "gameplay.construction_production.maintenance_state_obligation_cancelled",
            "projection_scope": "project",
        },
        "write_path": "semantic proposal -> closed Construction action route -> Construction fragment -> ObligationSettlementCoordinator.cancel SettlementPlan -> one GameplayEventStore.append_batch -> project outbox/replay/scoped projection",
        "limitations": [
            "Only effect:maintenance_state_dispel over an existing project-scoped state:maintenance_due with its committed open obligation is admitted.",
            "Cancellation is not generally enabled for the Construction maintenance lifecycle; only the exact semantic action registration exposes it.",
            "Transform, repair, payment, material and service-completion semantics remain unsupported and zero-write.",
        ],
    }
    path = verification_dir(root) / "infra-construction-maintenance-state-action-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1P Construction Maintenance State Action Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_construction_maintenance_state_action_report_json={path}")
    print(f"overall_infra_construction_maintenance_state_action_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
