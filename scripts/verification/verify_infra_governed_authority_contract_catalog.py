from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    catalog = root / "backend" / "tests" / "test_infra_governed_authority_contract_catalog.py"
    government = root / "backend" / "tests" / "test_infra_government_policy_registration.py"
    debt = root / "backend" / "tests" / "test_infra_debt_settlement_formal_spine.py"
    ecology = root / "backend" / "tests" / "test_infra_ecology_weather_front_organization_supply_edge.py"
    promotion = root / "backend" / "tests" / "test_infra_organization_supply_promotion.py"
    cases = {
        "five_fixed_contracts": (catalog, "test_catalog_materializes_only_existing_cross_inf_owner_contracts"),
        "unknown_kind_zero_write_admission": (catalog, "test_catalog_rejects_unknown_or_kind_mismatched_contract_without_registration_surface"),
        "owner_stream_event_privacy_fence": (catalog, "test_catalog_rejects_owner_stream_event_or_privacy_mismatch"),
        "government_policy_preappend_contract": (government, "test_government_policy_registration_rejects_catalog_admission_failure_before_append"),
        "debt_settlement_formal_contract": (debt, "test_simple_debt_payment_uses_formal_owner_fragments_and_redacted_outbox"),
        "debt_owner_replay_reader": (catalog, "test_simple_debt_catalog_replay_reader_is_exposed_by_owner_service"),
        "ecology_organization_consumer_contract": (ecology, "test_weather_front_organization_supply_edge_uses_existing_organization_fragment_and_one_append"),
        "organization_branch_promotion_contract": (promotion, "test_organization_promotes_one_durable_supply_into_existing_production_stream"),
    }
    checks, evidence = {}, []
    for check, (test_file, selector) in cases.items():
        log_path = verification_dir(root) / f"infra-governed-authority-contract-catalog-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_file}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-governed-authority-contract-catalog",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "evidence": evidence,
        "run_id": f"infra-governed-authority-contract-catalog-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "limitations": [
            "The catalog is read-only and cannot register or append contracts.",
            "Arbitrary policy, settlement, ecology fanout, promotion and population truth remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-governed-authority-contract-catalog-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF Governed Authority Contract Catalog Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
