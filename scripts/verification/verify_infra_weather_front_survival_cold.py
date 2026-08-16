from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_weather_front_survival_cold.py"
    cases = {
        "existing_survival_owner_append": "test_weather_front_cold_survival_owner_commits_existing_state_events",
        "forged_source_zero_write": "test_weather_front_cold_rejects_forged_source_without_write",
        "nonproject_scope_zero_write": "test_weather_front_cold_rejects_nonproject_scope_without_write",
        "wrong_weather_zero_write": "test_weather_front_cold_rejects_nonfrost_weather_without_write",
        "region_mismatch_zero_write": "test_weather_front_cold_rejects_region_mismatched_assignment_without_write",
        "duplicate_idempotency": "test_weather_front_cold_duplicate_is_idempotent",
        "target_revision_zero_write": "test_weather_front_cold_rejects_stale_survival_revision_without_write",
        "ecology_revision_zero_write": "test_weather_front_cold_rejects_stale_ecology_revision_without_write",
        "population_revision_zero_write": "test_weather_front_cold_rejects_stale_population_revision_without_write",
        "changed_duplicate_zero_write": "test_weather_front_cold_rejects_changed_duplicate_without_write",
        "outbox_privacy": "test_weather_front_cold_outbox_is_project_scoped_and_redacted",
        "checkpoint_tail_replay": "test_weather_front_cold_full_and_checkpoint_tail_replay_match",
        "private_source_zero_write": "test_weather_front_cold_rejects_private_ecology_source_without_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-weather-front-survival-cold-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-weather-front-survival-cold",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-weather-front-survival-cold-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["EcologyHazardAuthority", "ProfileActivationAuthority", "SurvivalAuthority"],
        "source_stream": "gameplay:ecology:{source_region_ref}",
        "assignment_stream": "population:{world_ref}",
        "target_stream": "gameplay:survival:{profile_ref}",
        "write_path": "Ecology evidence + activation projection -> SurvivalAuthority -> GameplayCommandEnvelope -> existing Survival events -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection",
        "receipt_boundary": "Only the Survival append result is returned; Ecology and Activation evidence writes retain their own append results and never merge into a cross-stream receipt.",
        "limitations": [
            "Only project-visible weather:frost can enter the existing effect:cold_exposure to state:cold row for one assigned active profile.",
            "No generic weather mapping, consumer registry, fanout, retry, compensation, scheduler, population truth owner, NPC/social truth store, SOC, GAME, P6, or P7 work is admitted."
        ]
    }
    path = verification_dir(root) / "infra-weather-front-survival-cold-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1AC Weather-front Survival Cold Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_weather_front_survival_cold_report_json={path}")
    print(f"overall_infra_weather_front_survival_cold_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
