from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "authorized_snapshot_delivery": (
            "backend/tests/test_infra_weather_front_government_drought_advisory_presentation.py",
            "test_project_granted_jurisdiction_receives_only_fixed_advisory_snapshot_and_delivery",
        ),
        "scope_and_transport_zero_leak": (
            "backend/tests/test_infra_weather_front_government_drought_advisory_presentation.py",
            "test_foreign_scope_wrong_outbox_and_disconnected_session_are_zero_leak",
        ),
        "post_commit_dispatch": (
            "backend/tests/test_websocket_connection_context.py",
            "test_dispatched_government_advisory_outbox_delivers_only_to_the_bound_presentation_session",
        ),
        "receipt_and_no_actor_facade": (
            "backend/tests/test_godot_gameplay_mirror_delivery.py",
            "test_connection_registry_delivers_fixed_government_advisory_without_an_actor_facade",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative_test_path, test_name) in cases.items():
        test_path = root / relative_test_path
        log_path = verification_dir(root) / f"infra-weather-front-government-drought-advisory-presentation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-weather-front-government-drought-advisory-presentation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _name in cases.values()}),
        "evidence": evidence,
        "run_id": f"infra-weather-front-government-drought-advisory-presentation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "read_path": "committed Government advisory -> existing outbox dispatch -> server-issued jurisdiction binding -> fixed WebSocket/Godot presentation projection",
        "limitations": [
            "This is a project/jurisdiction read-side extension of the fixed Government advisory row, not a new truth owner or event.",
            "It cannot use actor scope as a jurisdiction substitute or expose a caller-selected jurisdiction.",
        ],
    }
    path = verification_dir(root) / "infra-weather-front-government-drought-advisory-presentation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3R Government Drought Advisory Presentation Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_weather_front_government_drought_advisory_presentation_report_json={path}")
    print(f"overall_infra_weather_front_government_drought_advisory_presentation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
