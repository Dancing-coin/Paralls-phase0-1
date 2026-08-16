from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_ecology_weather_front_propagation.py"
    cases = {
        "one_step_owner_batch": "test_weather_front_propagates_one_project_visible_neighbor_step_in_one_existing_append_batch",
        "revision_conflict_zero_write": "test_weather_front_rejects_stale_revision_without_writes",
        "adjacency_zero_write": "test_weather_front_rejects_asymmetric_neighbor_without_writes",
        "idempotency": "test_weather_front_is_idempotent",
        "privacy_zero_write": "test_weather_front_rejects_nonproject_scope_without_writes",
        "project_outbox_scope": "test_weather_front_outbox_is_project_scoped",
        "checkpoint_tail_replay": "test_weather_front_checkpoint_tail_replay_matches_full_replay",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-propagation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-propagation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-ecology-weather-front-propagation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "authority:ecology / EcologyHazardAuthority",
        "streams": ["gameplay:ecology:{source_region_ref}", "gameplay:ecology:{target_region_ref}"],
        "write_path": "EcologyHazardAuthority -> GameplayCommandEnvelope -> two OwnerAuthorizedFragments -> one GameplayEventStore.append_batch -> project outbox/replay -> scoped projection",
        "limitations": [
            "One symmetric-neighbor, one-step, budget-one weather propagation only; caller-driven and not a scheduler.",
            "No fanout, multi-hop, hazard, obligation, retry, compensation, consumer edge, or non-ecology domain write is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-propagation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3C Ecology Weather-Front Propagation Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_weather_front_propagation_report_json={path}")
    print(f"overall_infra_ecology_weather_front_propagation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
