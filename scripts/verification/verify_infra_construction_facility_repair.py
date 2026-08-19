from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_construction_facility_repair.py"
    cases = {
        "repair_success_receipt": "test_facility_repair_appends_owner_event_and_projects_condition",
        "exact_duplicate_idempotency": "test_facility_repair_exact_duplicate_is_receipt_replay_without_write",
        "changed_duplicate_zero_write": "test_facility_repair_changed_duplicate_is_zero_write",
        "revision_privacy_amount_zero_write": "test_facility_repair_rejections_are_zero_write",
        "compensation_receipt": "test_facility_repair_compensation_restores_prior_condition",
        "compensation_duplicate_idempotency": "test_facility_repair_compensation_exact_duplicate_replays_receipt_without_write",
        "full_checkpoint_tail_replay": "test_facility_repair_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-facility-repair-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-facility-repair",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-facility-repair-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "event_types": [
                "gameplay.construction_production.facility_repaired",
                "gameplay.construction_production.facility_repair_compensated",
            ],
            "projection_scope": "project",
        },
        "write_path": "GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> ConstructionProductionAuthority.projector/outbox",
        "limitations": [
            "Repair is bounded to one existing Construction facility stream and one explicit compensation of the latest repair.",
            "No payment, account, transform, material, service-completion, or generic action semantics are admitted.",
        ],
    }
    path = verification_dir(root) / "infra-construction-facility-repair-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AE Construction Facility Repair Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_construction_facility_repair_report_json={path}")
    print(f"overall_infra_construction_facility_repair_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
