from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_weather_front_wave_fanout.py"
    cases = {
        "two_wave_single_batch_and_projection": "test_weather_front_wave_fanout_commits_two_levels_in_one_ecology_batch",
        "exact_duplicate_idempotency": "test_weather_front_wave_fanout_replays_exact_duplicate_without_second_write",
        "changed_duplicate_zero_write": "test_weather_front_wave_fanout_rejects_changed_duplicate_without_write",
        "stale_revision_zero_write": "test_weather_front_wave_fanout_rejects_stale_revision_without_write",
        "invalid_second_wave_zero_write": "test_weather_front_wave_fanout_rejects_invalid_second_wave_source_without_write",
        "nonadjacent_edge_zero_write": "test_weather_front_wave_fanout_rejects_nonadjacent_edge_without_write",
        "privacy_scope_zero_write": "test_weather_front_wave_fanout_rejects_nonproject_scope_without_write",
        "project_outbox_privacy": "test_weather_front_wave_fanout_outbox_is_project_scoped_and_redacted",
        "full_checkpoint_tail_replay": "test_weather_front_wave_fanout_replays_full_and_checkpoint_tail_projection",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-wave-fanout-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-wave-fanout",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-ecology-weather-front-wave-fanout-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "authority:ecology",
        "stream": "gameplay:ecology:{region_ref}",
        "event_family": ["weather_front.propagated", "environment.recorded"],
        "write_path": "EcologyHazardAuthority -> owner fragments -> one GameplayEventStore.append_batch -> project outbox/replay -> regional projection",
        "limitations": [
            "This is a caller-driven two-wave plan capped at six Ecology-only edges, not autonomous or unbounded propagation.",
            "The only cross-domain consumer edges remain the two already registered Construction edges.",
            "No third consumer, scheduler, retry, compensation, generic graph runtime, or non-Ecology write is admitted."
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-wave-fanout-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3F Ecology Weather-Front Wave Fanout Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_ecology_weather_front_wave_fanout_report_json={path}")
    print(f"overall_infra_ecology_weather_front_wave_fanout_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
