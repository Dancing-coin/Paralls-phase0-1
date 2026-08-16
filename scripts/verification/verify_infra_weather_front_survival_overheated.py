from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    heat_tests = root / "backend" / "tests" / "test_infra_weather_front_survival_overheated.py"
    catalog_tests = root / "backend" / "tests" / "test_infra_governed_authority_contract_catalog.py"
    cases = {
        "existing_survival_owner_append": (heat_tests, "test_weather_front_heat_survival_owner_commits_existing_state_events"),
        "wrong_weather_zero_write": (heat_tests, "test_weather_front_heat_rejects_wrong_weather_without_write"),
        "forged_source_zero_write": (heat_tests, "test_weather_front_heat_rejects_forged_source_without_write"),
        "nonproject_scope_zero_write": (heat_tests, "test_weather_front_heat_rejects_nonproject_scope_without_write"),
        "ecology_revision_zero_write": (heat_tests, "test_weather_front_heat_rejects_stale_ecology_revision_without_write"),
        "population_revision_zero_write": (heat_tests, "test_weather_front_heat_rejects_stale_population_revision_without_write"),
        "target_revision_zero_write": (heat_tests, "test_weather_front_heat_rejects_stale_survival_revision_without_write"),
        "duplicate_idempotency": (heat_tests, "test_weather_front_heat_duplicate_is_idempotent"),
        "changed_duplicate_zero_write": (heat_tests, "test_weather_front_heat_rejects_changed_duplicate_without_write"),
        "outbox_checkpoint_tail_replay": (heat_tests, "test_weather_front_heat_outbox_and_replay_are_project_scoped"),
        "private_source_zero_write": (heat_tests, "test_weather_front_heat_rejects_private_ecology_source_without_write"),
        "catalog_row_admission": (catalog_tests, "test_catalog_materializes_only_existing_cross_inf_owner_contracts"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-weather-front-survival-overheated-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-weather-front-survival-overheated",
        "canonical_package": "INF-1AD (INF-1)",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(heat_tests.relative_to(root)).replace("\\", "/"),
            str(catalog_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": evidence,
        "run_id": f"infra-weather-front-survival-overheated-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["EcologyHazardAuthority", "ProfileActivationAuthority", "SurvivalAuthority"],
        "source_stream": "gameplay:ecology:{source_region_ref}",
        "assignment_stream": "population:{world_ref}",
        "target_stream": "gameplay:survival:{profile_ref}",
        "event_family": ["gameplay.survival.state_applied", "gameplay.survival.obligation_opened"],
        "write_path": "Ecology evidence + activation projection -> SurvivalAuthority -> GameplayCommandEnvelope -> existing Survival events -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection",
        "receipt_boundary": "Only the Survival append result is returned; Ecology and Activation evidence writes retain their own append results and never merge into a cross-stream receipt.",
        "limitations": [
            "Only project-visible weather:heat can enter the existing effect:heat_exposure to state:overheated row for one assigned active profile.",
            "This is one exact source edge, not a generic weather mapping, consumer registry, fanout, retry, compensation, scheduler, population truth owner, NPC/social truth store, SOC, GAME, P6, or P7 capability.",
        ],
    }
    path = verification_dir(root) / "infra-weather-front-survival-overheated-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AD Weather-front Survival Overheated Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_weather_front_survival_overheated_report_json={path}")
    print(f"overall_infra_weather_front_survival_overheated_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
