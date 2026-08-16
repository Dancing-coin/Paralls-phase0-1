from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_construction_maintenance_state_obligation.py"
    cases = {
        "owner_open_due_settle_append": "test_construction_maintenance_state_opens_event_derived_obligation_and_settles_due_expiry",
        "unknown_source_zero_write": "test_construction_maintenance_state_obligation_rejects_unknown_source_without_write",
        "duplicate_source_zero_write": "test_construction_maintenance_state_obligation_rejects_duplicate_source_without_write",
        "stale_revision_zero_write": "test_construction_maintenance_state_obligation_rejects_stale_revision_without_write",
        "wrong_source_zero_write": "test_construction_maintenance_state_obligation_rejects_wrong_source_without_write",
        "exact_duplicate_idempotency": "test_construction_maintenance_state_obligation_replays_exact_open_without_write",
        "changed_duplicate_revision_zero_write": "test_construction_maintenance_state_obligation_rejects_duplicate_with_changed_revision_without_write",
        "changed_duplicate_due_tick_zero_write": "test_construction_maintenance_state_obligation_rejects_duplicate_with_changed_due_tick_without_write",
        "settlement_requires_committed_open": "test_construction_maintenance_state_obligation_rejects_settlement_without_committed_open",
        "settled_only_fragment_zero_write": "test_construction_maintenance_state_obligation_rejects_settled_only_fragment_without_write",
        "non_owner_fragment_zero_write": "test_construction_maintenance_state_obligation_rejects_non_owner_fragment_without_write",
        "single_active_obligation_zero_write": "test_construction_maintenance_state_reapply_cannot_open_a_second_active_obligation",
        "cancel_unsupported_zero_write": "test_construction_maintenance_state_obligation_rejects_cancel_without_write",
        "retry_unsupported_zero_write": "test_construction_maintenance_state_obligation_rejects_retry_without_write",
        "compensation_unsupported_zero_write": "test_construction_maintenance_state_obligation_rejects_compensation_without_write",
        "lifecycle_projection_open_to_settled": "test_construction_maintenance_state_obligation_projects_open_then_settled_lifecycle",
        "project_scoped_outbox": "test_construction_maintenance_state_obligation_emits_project_scoped_outbox",
        "append_derived_receipt_privacy": "test_construction_maintenance_state_obligation_receipt_is_append_derived",
        "full_checkpoint_tail_replay": "test_construction_maintenance_state_obligation_replays_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-maintenance-state-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-maintenance-state-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-maintenance-state-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "ConstructionProductionAuthority",
        "stream": "gameplay:construction_production:{facility_ref}",
        "events": [
            "gameplay.construction_production.maintenance_state_applied",
            "gameplay.construction_production.maintenance_state_obligation_opened",
            "gameplay.construction_production.maintenance_state_expired",
            "gameplay.construction_production.maintenance_state_obligation_settled",
        ],
        "write_path": "semantic proposal -> ConstructionProductionAuthority -> GameplayCommandEnvelope / SettlementPlan -> GameplayEventStore.append_batch -> project outbox -> Construction projection/replay",
        "limitations": [
            "Only effect:maintenance_required -> state:maintenance_due and policy:construction_maintenance_state_expiry@1 are admitted.",
            "Retry, cancellation, compensation, dispel, transform, dynamic policy registration, generic owner dispatch, and scheduler behavior are unsupported by this package.",
        ],
    }
    path = verification_dir(root) / "infra-construction-maintenance-state-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1N Construction Maintenance State Obligation Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_construction_maintenance_state_obligation_report_json={path}")
    print(f"overall_infra_construction_maintenance_state_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
