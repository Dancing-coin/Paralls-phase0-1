from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_weather_front_construction_edge.py"
    cases = {
        "target_owner_success": "test_weather_front_construction_edge_writes_existing_maintenance_event_only",
        "closed_admission_zero_write": "test_weather_front_construction_edge_rejects_missing_or_forged_admission_without_writes",
        "target_idempotency": "test_weather_front_construction_edge_exact_duplicate_replays_without_second_write",
        "target_revision_zero_write": "test_weather_front_construction_edge_rejects_stale_target_revision_without_writes",
        "source_revision_zero_write": "test_weather_front_construction_edge_rejects_stale_ecology_source_without_target_write",
        "changed_duplicate_zero_write": "test_weather_front_construction_edge_rejects_changed_duplicate_without_writes",
        "source_privacy_zero_write": "test_weather_front_construction_edge_rejects_private_source_without_writes",
        "project_outbox_privacy": "test_weather_front_construction_edge_outbox_is_project_scoped_and_redacted",
        "full_checkpoint_tail_replay": "test_weather_front_construction_edge_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-construction-edge-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-construction-edge",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-construction-edge-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "EcologyHazardAuthority",
        "target_owner": "ConstructionProductionAuthority",
        "source_stream": "gameplay:ecology:{region_ref}",
        "target_stream": "gameplay:construction_production:{facility_ref}",
        "event_family": ["gameplay.ecology.weather_front.propagated", "gameplay.construction_production.maintenance_obligation_created"],
        "write_path": "Ecology proposal/admission -> Construction source revalidation -> Construction owner fragment -> one GameplayEventStore.append_batch -> project outbox/replay/scoped projection",
        "limitations": [
            "Only ecology-weather:front-to-construction-maintenance:v1 is admitted by this profile.",
            "No generic consumer registry, scheduler, retry/compensation, Economy/Organization consumer, SOC, GAME, P6, or P7 is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-construction-edge-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3G Weather-Front Construction Edge Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_weather_front_construction_edge_report_json={path}")
    print(f"overall_infra_ecology_weather_front_construction_edge_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
