from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    catalog = root / "backend" / "tests" / "test_infra_governed_authority_contract_catalog.py"
    construction = root / "backend" / "tests" / "test_infra_ecology_weather_front_construction_edge.py"
    fanout = root / "backend" / "tests" / "test_infra_ecology_weather_front_construction_fanout.py"
    organization = root / "backend" / "tests" / "test_infra_ecology_weather_front_organization_supply_edge.py"
    economy = root / "backend" / "tests" / "test_infra_ecology_weather_front_economy_quote_edge.py"
    economy_fanout = root / "backend" / "tests" / "test_infra_ecology_weather_front_economy_quote_fanout.py"
    cases = {
        "construction_contract_metadata": (
            catalog,
            "test_catalog_pins_weather_front_construction_consumer_contract_metadata",
        ),
        "organization_contract_metadata": (
            catalog,
            "test_catalog_pins_weather_front_organization_consumer_contract_metadata",
        ),
        "economy_contract_metadata": (
            catalog,
            "test_catalog_pins_weather_front_economy_quote_consumer_contract_metadata",
        ),
        "economy_fanout_contract_metadata": (
            catalog,
            "test_catalog_pins_weather_front_economy_quote_fanout_consumer_contract_metadata",
        ),
        "construction_preappend_zero_write": (
            construction,
            "test_weather_front_construction_catalog_mismatch_rejects_before_append",
        ),
        "organization_preappend_zero_write": (
            organization,
            "test_weather_front_organization_catalog_mismatch_rejects_before_append",
        ),
        "economy_preappend_zero_write": (
            economy,
            "test_weather_front_quote_catalog_mismatch_rejects_before_append",
        ),
        "economy_fanout_preappend_zero_write": (
            economy_fanout,
            "test_weather_front_quote_fanout_rejects_stale_source_missing_target_and_catalog_mismatch",
        ),
        "economy_two_quote_batch_contract": (
            economy_fanout,
            "test_weather_front_quote_fanout_updates_two_existing_quotes_in_one_owner_batch",
        ),
        "construction_two_facility_batch_contract": (
            fanout,
            "test_weather_front_construction_fanout_writes_two_existing_target_streams_in_one_batch",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_file, selector) in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-weather-front-owner-contract-matrix-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", f"{test_file}::{selector}"], root, log_path
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-weather-front-owner-contract-matrix",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({str(path.relative_to(root)).replace("\\", "/") for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"infra-ecology-weather-front-owner-contract-matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "limitations": [
            "The matrix has four source-controlled existing target-owner rows, including one fixed two-quote Economy fanout row.",
            "It does not register callers, widen fanout, add retry/compensation, or give Ecology another domain's writer authority.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-weather-front-owner-contract-matrix-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3L Weather-Front Owner-Contract Matrix Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
