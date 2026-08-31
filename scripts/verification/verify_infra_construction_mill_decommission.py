from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_construction_mill_decommission.py"
    cases = {
        "fixed_project_lifecycle_event_and_receipt": "test_mill_decommission_commits_only_fixed_project_lifecycle_event_and_receipt",
        "source_privacy_and_revision_zero_write": "test_mill_decommission_source_privacy_and_revision_conflicts_are_zero_write",
        "binding_admission_zero_write": "test_mill_decommission_binding_admission_rejections_are_zero_write",
        "active_run_zero_write": "test_mill_decommission_rejects_committed_started_run_without_releasing_or_compensating",
        "idempotency_full_tail_terminal": "test_mill_decommission_duplicate_replay_and_checkpoint_tail_are_terminal",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-mill-decommission-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-mill-decommission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-mill-decommission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "package_revision": "package:industrial-facilities:v3",
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "event_types": ["gameplay.construction_production.facility_decommissioned"],
            "projection_scope": "project",
        },
        "write_path": "GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> ConstructionProductionAuthority.projector/outbox",
        "limitations": [
            "Only active mill_reinforced facilities with exact committed v2 source evidence may transition.",
            "The v1 lifecycle is terminal: no reactivation, compensation, fanout, payment, material, output, maintenance, or cross-domain consequence.",
        ],
    }
    path = verification_dir(root) / "infra-construction-mill-decommission-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AH Construction Mill Decommission Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_construction_mill_decommission_report_json={path}")
    print(f"overall_infra_construction_mill_decommission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
