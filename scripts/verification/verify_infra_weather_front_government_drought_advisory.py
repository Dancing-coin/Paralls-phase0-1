from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_weather_front_government_drought_advisory.py"
    cases = {
        "fixed_advisory_receipt": "test_drought_weather_front_issues_one_fixed_government_advisory_and_receipt",
        "source_privacy_revision_zero_write": "test_drought_advisory_source_privacy_and_revision_fences_are_zero_write",
        "catalog_zero_write": "test_drought_advisory_catalog_mismatch_is_zero_write",
        "idempotency_and_replay": "test_drought_advisory_duplicate_receipt_and_checkpoint_tail_replay_are_fixed",
        "retry_after_source_advance": "test_drought_advisory_exact_duplicate_replays_after_ecology_source_advances",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-weather-front-government-drought-advisory-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-weather-front-government-drought-advisory",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-weather-front-government-drought-advisory-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "owner_ref": "actor_gameplay.government_domain",
            "source_event": "gameplay.ecology.weather_front.propagated",
            "target_stream": "gameplay:government:advisory:{jurisdiction_ref}",
            "target_event": "gameplay.government.drought_advisory_issued",
            "projection_scope": "project",
        },
        "write_path": "committed Ecology source + region pin -> GovernmentAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> Government advisory replay/outbox",
        "limitations": [
            "Only project-visible weather:drought fronts with exact Ecology region/jurisdiction pins issue an advisory.",
            "The advisory has no restriction, payment, material, production, population, compensation, retry, revocation, or fanout semantics.",
        ],
    }
    path = verification_dir(root) / "infra-weather-front-government-drought-advisory-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3R Weather-front Government Drought Advisory Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_weather_front_government_drought_advisory_report_json={path}")
    print(f"overall_infra_weather_front_government_drought_advisory_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
