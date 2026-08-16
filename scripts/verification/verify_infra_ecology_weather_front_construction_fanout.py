from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_weather_front_construction_fanout.py"
    cases = {
        "two_target_single_batch_success": "test_weather_front_construction_fanout_writes_two_existing_target_streams_in_one_batch",
        "closed_admission_zero_write": "test_weather_front_construction_fanout_rejects_missing_admission_without_write",
        "changed_duplicate_privacy_zero_write": "test_weather_front_construction_fanout_rejects_changed_duplicate_and_private_command_without_write",
        "idempotency_revision_privacy_replay": "test_weather_front_construction_fanout_is_revisioned_idempotent_private_and_replayable",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-construction-fanout-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-construction-fanout",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-construction-fanout-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "EcologyHazardAuthority",
        "target_owner": "ConstructionProductionAuthority",
        "source_stream": "gameplay:ecology:{region_ref}",
        "target_streams": ["gameplay:construction_production:{facility_ref}:a", "gameplay:construction_production:{facility_ref}:b"],
        "event_family": ["gameplay.ecology.weather_front.propagated", "gameplay.construction_production.maintenance_obligation_created"],
        "write_path": "Ecology proposal/opaque admission -> Construction two owner fragments -> one GameplayEventStore.append_batch -> project outbox/replay/scoped projections",
        "limitations": [
            "Exactly two existing Construction facilities are admitted; this is not a generic fanout registry.",
            "No Economy/Organization/social/population writer, scheduler, retry/compensation, generic promotion, SOC, GAME, P6, or P7 is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-construction-fanout-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3H Weather-Front Construction Fanout Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_weather_front_construction_fanout_report_json={path}")
    print(f"overall_infra_ecology_weather_front_construction_fanout_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
