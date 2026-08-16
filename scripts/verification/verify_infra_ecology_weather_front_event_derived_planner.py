from __future__ import annotations

from datetime import datetime, timezone
import json

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def _predecessor_report_is_fresh(
    report: dict[str, object],
    *,
    expected_profile: str,
    expected_commit: str,
) -> bool:
    return (
        report.get("profile") == expected_profile
        and report.get("overall_passed") is True
        and report.get("commit") == expected_commit
        and isinstance(report.get("run_id"), str)
        and bool(report.get("run_id"))
    )


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    current_commit = evidence_revision(root)
    test_path = root / "backend" / "tests" / "test_infra_ecology_weather_front_event_derived_planner.py"
    cases = {
        "deterministic_event_derived_proposal": "test_event_derived_planner_is_deterministic_and_does_not_accept_edges",
        "missing_source_zero_write": "test_event_derived_planner_rejects_missing_source_without_write",
        "private_source_zero_write": "test_event_derived_planner_rejects_private_source_without_write",
        "foreign_stream_source_zero_write": "test_event_derived_planner_rejects_foreign_stream_source_without_write",
        "malformed_source_zero_write": "test_event_derived_planner_rejects_malformed_negative_depth_source_without_write",
        "exhausted_frontier_zero_write": "test_event_derived_planner_rejects_exhausted_frontier_without_write",
        "owner_batch_success": "test_event_derived_planner_commits_via_existing_ecology_batch",
        "idempotency_and_changed_plan_zero_write": "test_event_derived_planner_exact_duplicate_and_changed_duplicate_are_zero_write",
        "revision_conflict_zero_write": "test_event_derived_planner_rejects_revision_conflict_without_write",
        "privacy_scope_zero_write": "test_event_derived_planner_rejects_nonproject_scope_without_write",
        "project_outbox_and_checkpoint_tail_replay": "test_event_derived_planner_outbox_and_checkpoint_tail_replay_are_scoped",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-event-derived-planner-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    predecessor_reports = {
        "regional_truth": root / ".harness" / "verification" / "infra-regional-ecology-truth-report.json",
        "wave_fanout": root / ".harness" / "verification" / "infra-ecology-weather-front-wave-fanout-report.json",
    }
    predecessor_profiles = {
        "regional_truth": "infra-regional-ecology-truth",
        "wave_fanout": "infra-ecology-weather-front-wave-fanout",
    }
    for name, path in predecessor_reports.items():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            checks[f"predecessor_{name}_report"] = _predecessor_report_is_fresh(
                report,
                expected_profile=predecessor_profiles[name],
                expected_commit=current_commit,
            )
        except (OSError, ValueError, TypeError):
            checks[f"predecessor_{name}_report"] = False
    report = {
        "profile": "infra-ecology-weather-front-event-derived-planner",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "predecessor_reports": {
            name: str(path.relative_to(root)).replace("\\", "/") for name, path in predecessor_reports.items()
        },
        "run_id": f"infra-ecology-weather-front-event-derived-planner-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": current_commit,
        "owner": "authority:ecology",
        "stream": "gameplay:ecology:{region_ref}",
        "event_family": ["gameplay.ecology.weather_front.propagated", "gameplay.ecology.environment.recorded"],
        "write_path": "EcologyHazardAuthority -> owner fragments -> one GameplayEventStore.append_batch -> project outbox/replay -> regional projection",
        "limitations": [
            "Planner derives at most two Ecology-only waves from one committed project-visible weather-front event.",
            "No scheduler, clock, generic graph runtime, consumer registry, cross-domain writer, or new truth store is admitted.",
            "Existing fixed Construction, Organization, and Economy consumer edges are unchanged."
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-event-derived-planner-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3M Ecology Event-Derived Weather-Front Planner Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_ecology_weather_front_event_derived_planner_report_json={path}")
    print(f"overall_infra_ecology_weather_front_event_derived_planner_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
