from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "contract_source_and_fulfillment": (
            "backend/tests/test_inf2ae_facility_commissioning_review_contract.py",
            "test_commissioning_review_fulfillment_has_fixed_evidence_and_replay",
        ),
        "contract_zero_write_and_generic_fence": (
            "backend/tests/test_inf2ae_facility_commissioning_review_contract.py",
            "test_commissioning_review_source_and_generic_contract_paths_are_zero_write",
        ),
        "package_digest_and_activation": (
            "backend/tests/test_inf2ae_facility_commissioning_review_package.py",
            "test_frozen_v4_commissioning_package_has_exact_digest_and_service_content",
        ),
        "fixed_economy_settlement_and_replay": (
            "backend/tests/test_inf2ae_facility_commissioning_review_exchange.py",
            "test_facility_commissioning_review_package_settles_once_with_fixed_price_and_replay",
        ),
        "price_account_and_duplicate_zero_write": (
            "backend/tests/test_inf2ae_facility_commissioning_review_exchange.py",
            "test_facility_commissioning_review_price_account_ambiguity_and_changed_duplicate_are_zero_write",
        ),
        "catalog_exactness": (
            "backend/tests/test_infra_governed_authority_contract_catalog.py",
            "test_catalog_materializes_only_existing_cross_inf_owner_contracts",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf2ae-facility-commissioning-review-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf2ae-facility-commissioning-review-exchange",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf2ae-facility-commissioning-review-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "committed INF-1AI facility operational verification -> Contract commissioning review -> fixed Economy package exchange",
        "limitations": [
            "The package is one immutable v4 content row; no generic service payment or transfer API is admitted.",
            "Construction, Contract, and Economy owners retain separate events, receipts, privacy and replay readers.",
        ],
    }
    path = verification_dir(root) / "inf2ae-facility-commissioning-review-exchange-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2AE Facility Commissioning Review Exchange Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf2ae_facility_commissioning_review_report_json={path}")
    print(f"overall_inf2ae_facility_commissioning_review_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
