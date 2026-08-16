from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_construction_maintenance_state_owner.py"
    cases = {
        "owner_state_append": "test_construction_maintenance_owner_row_appends_fixed_state_event",
        "duplicate_idempotency": "test_construction_maintenance_owner_row_replays_exact_duplicate_without_append",
        "changed_duplicate_zero_write": "test_construction_maintenance_owner_row_rejects_changed_duplicate_without_append",
        "revision_conflict_zero_write": "test_construction_maintenance_owner_row_rejects_stale_revision_without_append",
        "privacy_zero_write": "test_construction_maintenance_owner_row_rejects_nonproject_privacy_without_append",
        "mismatched_effect_zero_write": "test_construction_maintenance_owner_row_rejects_mismatched_pair_owner_or_stream_without_append[effect:wrong-state:maintenance_due-actor_gameplay.construction_production_domain-gameplay:construction_production:facility:bakery:1]",
        "mismatched_state_zero_write": "test_construction_maintenance_owner_row_rejects_mismatched_pair_owner_or_stream_without_append[effect:maintenance_required-state:wrong-actor_gameplay.construction_production_domain-gameplay:construction_production:facility:bakery:1]",
        "mismatched_owner_zero_write": "test_construction_maintenance_owner_row_rejects_mismatched_pair_owner_or_stream_without_append[effect:maintenance_required-state:maintenance_due-actor_gameplay.survival_domain-gameplay:construction_production:facility:bakery:1]",
        "mismatched_stream_zero_write": "test_construction_maintenance_owner_row_rejects_mismatched_pair_owner_or_stream_without_append[effect:maintenance_required-state:maintenance_due-actor_gameplay.construction_production_domain-gameplay:survival:facility:bakery:1]",
        "stale_semantic_vector_zero_write": "test_construction_maintenance_owner_row_rejects_nonexact_semantic_vector_without_append",
        "owner_mapping_zero_write": "test_construction_owner_rejects_direct_nonregistered_maintenance_effect_without_append",
        "owner_stale_semantic_vector_zero_write": "test_construction_owner_rejects_direct_stale_semantic_vector_without_append",
        "unacquired_facility_zero_write": "test_construction_maintenance_owner_row_rejects_unacquired_facility_without_append",
        "facility_without_run_settlement": "test_construction_maintenance_owner_row_settles_facility_without_started_run",
        "project_outbox_and_projection": "test_construction_maintenance_owner_row_emits_project_scoped_outbox_and_projection",
        "checkpoint_tail_replay": "test_construction_maintenance_owner_row_full_and_checkpoint_tail_projection_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-maintenance-state-owner-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", f"{test_path}::{test_name}"],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-maintenance-state-owner",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-maintenance-state-owner-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "ConstructionProductionAuthority",
        "stream": "gameplay:construction_production:{facility_ref}",
        "events": ["gameplay.construction_production.maintenance_state_applied"],
        "write_path": "semantic proposal -> ConstructionProductionAuthority-owned GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> scoped outbox -> construction projection checkpoint replay",
        "limitations": [
            "Only effect:maintenance_required -> state:maintenance_due is admitted by this package.",
            "No generic semantic dispatch, no alternate owner/stream/event selection, and no expiry, scheduler, or compensation lifecycle is enabled.",
        ],
    }
    path = verification_dir(root) / "infra-construction-maintenance-state-owner-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1G Construction Maintenance State Owner Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_construction_maintenance_state_owner_report_json={path}")
    print(f"overall_infra_construction_maintenance_state_owner_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
