from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_weather_front_survival_dehydration.py"
    cases = {
        "success_and_receipt": "test_weather_front_drought_survival_owner_commits_dehydration_state_and_receipt",
        "missing_source_zero_write": "test_weather_front_drought_rejects_missing_or_wrong_source_without_write",
        "assignment_privacy_zero_write": "test_weather_front_drought_rejects_assignment_mismatch_and_nonproject_scope_without_write",
        "revision_vector_zero_write": "test_weather_front_drought_rejects_stale_ecology_population_and_survival_revisions_without_write",
        "exact_and_changed_idempotency": "test_weather_front_drought_exact_and_changed_duplicate_have_fixed_idempotency_boundary",
        "outbox_privacy": "test_weather_front_drought_outbox_is_project_scoped_and_redacted",
        "full_replay": "test_weather_front_drought_full_and_checkpoint_tail_replay_match",
        "checkpoint_tail_replay": "test_weather_front_drought_full_and_checkpoint_tail_replay_match",
        "drought_process_rejected": "test_drought_process_advanced_is_not_a_weather_front_source_and_writes_nothing",
        "no_compensation_or_fanout": "test_weather_front_drought_has_no_compensation_or_fanout_event_vector",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-weather-front-survival-dehydration-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-weather-front-survival-dehydration",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-weather-front-survival-dehydration-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["EcologyHazardAuthority", "ProfileActivationAuthority", "SurvivalAuthority"],
        "source_stream": "gameplay:ecology:{source_region_ref}",
        "assignment_stream": "population:{world_ref}",
        "target_stream": "gameplay:survival:{profile_ref}",
        "write_path": "Ecology weather-front evidence + activation projection -> SurvivalAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch() -> project outbox/replay",
        "receipt_boundary": "Only the one Survival append result is returned; no Ecology append or cross-stream receipt is part of the capability.",
        "limitations": [
            "Only project-visible weather:drought can enter effect:dehydration_exposure to state:dehydrated for one assigned active profile.",
            "drought_process_advanced, compensation, fanout, generic routing, consumer registration, retry, and new runtime ownership remain excluded."
        ],
    }
    path = verification_dir(root) / "infra-weather-front-survival-dehydration-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3Q Weather-front Survival Dehydration Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_weather_front_survival_dehydration_report_json={path}")
    print(f"overall_infra_weather_front_survival_dehydration_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
