from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_survival_weather_front_blocker.py"
    selectors = {
        "closed_contract_matrix": "test_weather_front_survival_contract_matrix_remains_closed_to_four_existing_rows",
        "apply_zero_write": "test_weather_front_shaped_survival_apply_is_zero_write_without_owner_contract",
        "action_zero_write": "test_weather_front_shaped_survival_action_is_zero_write_without_owner_contract",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in selectors.items():
        log_path = verification_dir(root) / f"infra-survival-weather-front-blocker-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-survival-weather-front-blocker",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-survival-weather-front-blocker-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "SurvivalAuthority",
        "stream": "gameplay:survival:{actor_ref}",
        "write_path": "No admitted weather-front -> Survival write path; unsupported inputs reject before append_batch",
        "limitations": [
            "Only the existing cold/overheated/dehydrated/fatigued Survival rows are admitted.",
            "Weather-front provenance has no approved Survival owner/event/projection/receipt contract.",
        ],
    }
    path = verification_dir(root) / "infra-survival-weather-front-blocker-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1U Weather-front Survival Blocker Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_survival_weather_front_blocker_report_json={path}")
    print(f"overall_infra_survival_weather_front_blocker_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
