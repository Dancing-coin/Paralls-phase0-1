from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_weather_front_fanout.py"
    cases = {
        "three_target_one_append_projection": "test_weather_front_fanout_commits_three_targets_and_preserves_all_project_edges",
        "exact_duplicate_idempotency": "test_weather_front_fanout_replays_exact_duplicate_without_write",
        "changed_duplicate_zero_write": "test_weather_front_fanout_rejects_changed_duplicate_without_writes",
        "stale_revision_zero_write": "test_weather_front_fanout_rejects_stale_revision_without_writes",
        "duplicate_target_zero_write": "test_weather_front_fanout_rejects_duplicate_target_without_writes",
        "privacy_scope_zero_write": "test_weather_front_fanout_rejects_nonproject_scope_without_writes",
        "full_checkpoint_tail_replay": "test_weather_front_fanout_replays_full_and_checkpoint_tail_projection",
    }
    checks: dict[str, bool] = {}; evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-fanout-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0; evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-fanout", "overall_passed": all(checks.values()), "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")], "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-fanout-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root),
        "owner": "authority:ecology", "stream_pattern": "gameplay:ecology:{region_ref}",
        "write_path": "EcologyHazardAuthority -> GameplayCommandEnvelope -> existing Ecology stream fragments -> one GameplayEventStore.append_batch -> project outbox/replay/scoped projection",
        "limitations": ["Only one caller-named root plus one to three direct symmetric Ecology neighbors is admitted.", "No multi-round fanout, scheduler, consumer edge, or non-Ecology write is admitted."],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-fanout-report.json"; write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3E Ecology Weather-Front Fanout Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_weather_front_fanout_report_json={path}"); print(f"overall_infra_ecology_weather_front_fanout_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
