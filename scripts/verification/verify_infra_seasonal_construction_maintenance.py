from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_process_lifecycle.py"
    cases = {
        "seasonal_source_to_target_owner_success": "test_seasonal_process_proposes_only_one_admitted_construction_maintenance_fragment",
        "closed_admission_zero_write": "test_seasonal_maintenance_requires_exact_closed_admission_without_writes",
        "stale_source_zero_write": "test_seasonal_maintenance_rejects_stale_ecology_source_without_target_write",
        "target_idempotency": "test_seasonal_maintenance_is_idempotent",
        "target_revision_zero_write": "test_seasonal_maintenance_rejects_stale_target_revision_without_writes",
        "outbox_privacy": "test_seasonal_maintenance_project_outbox_redacts_ecology_provenance",
        "checkpoint_tail_replay": "test_seasonal_maintenance_checkpoint_tail_replay_matches_full_replay",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-seasonal-construction-maintenance-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-seasonal-construction-maintenance",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-seasonal-construction-maintenance-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "EcologyHazardAuthority",
        "target_owner": "ConstructionProductionAuthority",
        "source_stream": "gameplay:ecology:{region_ref}",
        "target_stream": "gameplay:construction_production:{facility_ref}",
        "write_path": "Ecology proposal/admission -> Construction source revalidation -> Construction owner fragment -> GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": [
            "Only ecology-process:seasonal-to-construction-maintenance:v1 is admitted.",
            "No generic propagation, scheduler, fanout, retry/compensation, market/body/social/population consumer, SOC, GAME, P6, or P7 is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-seasonal-construction-maintenance-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3B Seasonal Construction Maintenance Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_seasonal_construction_maintenance_report_json={path}")
    print(f"overall_infra_seasonal_construction_maintenance_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
