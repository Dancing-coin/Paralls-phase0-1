from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_ecology_weather_front_organization_supply_edge.py"
    selectors = {
        "owner_append_and_projection": "test_weather_front_organization_supply_edge_uses_existing_organization_fragment_and_one_append",
        "duplicate_and_changed_duplicate": "test_weather_front_organization_supply_edge_replays_exact_duplicate_and_rejects_changed_duplicate",
        "zero_write_admission_privacy_revision": "test_weather_front_organization_supply_edge_rejects_forged_privacy_and_stale_source_without_writes",
        "full_checkpoint_tail_replay": "test_weather_front_organization_supply_edge_replays_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, selector in selectors.items():
        log = verification_dir(root) / f"infra-ecology-weather-front-organization-supply-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-organization-supply-edge",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-organization-supply-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "EcologyHazardAuthority",
        "target_owner": "OrganizationAuthority",
        "target_stream": "gameplay:organization:{organization_ref}",
        "target_event": "gameplay.organization.commerce_commitment_accepted",
        "write_path": "Ecology admission -> OrganizationAuthority fragment -> GameplayCommandEnvelope/SettlementPlan -> one GameplayEventStore.append_batch -> project outbox/replay",
        "limitations": [
            "Only the fixed weather-front-to-Organization supply commitment edge is admitted.",
            "No generic consumer registry, direct Ecology organization write, payment, retry/compensation, or arbitrary fanout is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-organization-supply-edge-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3I Weather-Front Organization Supply Edge Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_ecology_weather_front_organization_supply_edge_report_json={path}")
    print(f"overall_infra_ecology_weather_front_organization_supply_edge_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
