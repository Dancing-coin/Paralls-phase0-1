from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_world_mode.py"
    cases = {
        "frozen_social_contract": "test_inf4r_freezes_social_view_recipient_time_digest_and_source_vector",
        "stale_source_zero_write": "test_inf4r_frozen_social_input_rejects_stale_source_vector_without_writes",
        "deterministic_social_plan": "test_inf4r_planner_pins_social_view_digest_into_deterministic_plan",
        "unsupported_inputs_zero_write": "test_inf4r_planner_rejects_unsupported_schedule_or_capability_inputs_without_writes",
        "capability_owner_view_consumer_zero_write": "test_inf4y_capability_owner_view_is_rejected_before_population_source_admission_without_writes",
        "social_input_digest": "test_inf4r_social_input_digest_binds_recipient_time_and_source_vector",
        "recipient_scope_zero_write": "test_inf4r_planner_rejects_candidate_outside_social_recipient_scope_without_writes",
        "legacy_merge_stale_social_zero_write": "test_inf4r_legacy_merge_rejects_stale_frozen_social_proposal_without_write",
        "social_source_full_checkpoint_tail_replay": "test_inf4r_social_source_replays_full_and_checkpoint_tail_without_legacy_merge_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-population-world-mode-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-population-world-mode",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-population-world-mode-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "SocialFactAuthority.view_for",
        "write_path": "SocialFactAuthority.view_for -> FrozenSocialPlanningInput -> PopulationPlanner proposal; legacy PopulationBatchPlan merge is zero-write, while formal writes require a separately admitted existing owner fragment/SettlementPlan path",
        "limitations": ["No household, organization, innovation, or civilization capability input is admitted by the INF-4R social proposal path.", "No new population owner, runtime, scheduler, or truth store is created."],
    }
    path = verification_dir(root) / "infra-population-world-mode-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4R Population World-Mode Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_population_world_mode_report_json={path}")
    print(f"overall_infra_population_world_mode_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
