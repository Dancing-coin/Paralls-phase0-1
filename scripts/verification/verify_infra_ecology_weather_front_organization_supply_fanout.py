from __future__ import annotations

from datetime import datetime, timezone

from common import (
    evidence_revision,
    repo_root,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = (
        root
        / "backend"
        / "tests"
        / "test_infra_ecology_weather_front_organization_supply_fanout.py"
    )
    selectors = {
        "owner_batch": "test_weather_front_organization_supply_fanout_updates_two_existing_organizations_in_one_owner_batch",
        "admission_and_arity": "test_weather_front_organization_supply_fanout_requires_exact_opaque_two_organization_admission",
        "catalog_source_revision": "test_weather_front_organization_supply_fanout_rejects_catalog_mismatch_source_conflict_and_revision_zero_write",
        "idempotency_privacy_replay": "test_weather_front_organization_supply_fanout_duplicate_privacy_and_replay_are_verified",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, selector in selectors.items():
        log = (
            verification_dir(root)
            / f"infra-ecology-weather-front-organization-supply-fanout-{name}.log"
        )
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{selector}"], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-organization-supply-fanout",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-organization-supply-fanout-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "source_owner": "EcologyHazardAuthority",
        "target_owner": "OrganizationAuthority",
        "target_streams": (
            "gameplay:organization:{organization_ref_a}",
            "gameplay:organization:{organization_ref_b}",
        ),
        "target_event": "gameplay.organization.commerce_commitment_accepted",
        "write_path": "Ecology opaque pair admission -> two existing OrganizationAuthority fragments -> one GameplayCommandEnvelope/SettlementPlan append_batch spine -> project outbox/replay",
        "limitations": [
            "Only one exact weather-front-to-two-Organization supply fanout row is admitted.",
            "No generic consumer registry, scheduler, payment, pricing, arbitrary target list, or new owner/store is admitted.",
        ],
    }
    path = (
        verification_dir(root)
        / "infra-ecology-weather-front-organization-supply-fanout-report.json"
    )
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3O Weather-Front Organization Supply Fanout Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_ecology_weather_front_organization_supply_fanout_report_json={path}")
    print(
        "overall_infra_ecology_weather_front_organization_supply_fanout_passed="
        f"{report['overall_passed']}"
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
