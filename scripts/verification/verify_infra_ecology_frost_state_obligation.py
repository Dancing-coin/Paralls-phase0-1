from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_frost_state_obligation.py"
    cases = {
        "apply_on_existing_ecology_stream": "test_ecology_frost_crop_state_apply_commits_on_existing_ecology_stream",
        "refresh_closed_row": "test_ecology_frost_crop_state_refresh_updates_due_without_reopening_the_row",
        "exact_duplicate_no_second_append": "test_ecology_frost_crop_state_duplicate_replays_without_second_append",
        "changed_duplicate_zero_write": "test_ecology_frost_crop_state_changed_duplicate_is_zero_write",
        "revision_conflict_zero_write": "test_ecology_frost_crop_state_revision_conflict_is_zero_write",
        "privacy_zero_write": "test_ecology_frost_crop_state_nonproject_privacy_is_zero_write",
        "authority_only_source_zero_write": "test_ecology_frost_crop_state_authority_only_source_is_zero_write",
        "unknown_row_zero_write": "test_ecology_frost_crop_state_unknown_row_is_zero_write",
        "due_expiry_through_coordinator": "test_ecology_frost_crop_state_due_expiry_settles_through_existing_coordinator",
        "project_scoped_outbox": "test_ecology_frost_crop_state_outbox_is_project_scoped",
        "full_replay": "test_ecology_frost_crop_state_full_replay_rebuilds_committed_history",
        "checkpoint_tail_replay": "test_ecology_frost_crop_state_checkpoint_tail_replay_matches_full_replay",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-frost-state-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-frost-state-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-frost-state-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "EcologyHazardAuthority",
        "stream": "gameplay:ecology:{region_ref}",
        "policy": "policy:ecology_frost_crop_state_expiry@1",
        "write_path": "EcologyHazardAuthority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only effect:frost -> state:frosted@1 is admitted.",
            "This package adds no scheduler, retry, compensation, consumer edge, or generic effect/state routing.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-frost-state-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1L Ecology Frost State Obligation Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_ecology_frost_state_obligation_report_json={path}")
    print(f"overall_infra_ecology_frost_state_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
