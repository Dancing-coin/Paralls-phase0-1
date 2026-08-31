from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "frozen_v2_package": ("backend/tests/test_inf2ad_municipal_drought_assessment_package.py", "test_frozen_municipal_drought_assessment_package_has_exact_v2_content_and_digest_pins"),
        "activation_and_digest_zero_write": ("backend/tests/test_inf2ad_municipal_drought_assessment_package.py", "test_frozen_package_activates_as_immutable_v2_content_and_tampering_is_zero_write"),
        "service_settlement_receipt_replay": ("backend/tests/test_inf2ad_municipal_drought_assessment_exchange.py", "test_exact_completed_municipal_drought_assessment_settles_once_with_fixed_policy_and_replay"),
        "price_and_duplicate_zero_write": ("backend/tests/test_inf2ad_municipal_drought_assessment_exchange.py", "test_wrong_service_evidence_and_changed_or_price_mismatched_duplicate_are_zero_write"),
        "same_currency_account_ambiguity_zero_write": ("backend/tests/test_inf2ad_municipal_drought_assessment_exchange.py", "test_multiple_same_currency_provider_accounts_are_zero_write"),
        "contract_generic_completion_zero_write": ("backend/tests/test_inf2ad_municipal_drought_assessment_exchange.py", "test_contract_owner_rejects_generic_municipal_assessment_evidence_before_exchange"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf2ad-municipal-drought-assessment-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf2ad-municipal-drought-assessment-exchange",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf2ad-municipal-drought-assessment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "fulfilled exact municipal drought assessment service -> existing Economy package exchange settlement",
        "limitations": ["No advisory, weather, inventory, material, permit, social, compensation, or generic service-payment fact is written.", "The v2 package has no capability binding request because platform schema 1.0 cannot truthfully map a declaration to an outer economic outcome."],
    }
    path = verification_dir(root) / "inf2ad-municipal-drought-assessment-exchange-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2AD Municipal Drought Assessment Exchange Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"inf2ad_municipal_drought_assessment_report_json={path}")
    print(f"overall_inf2ad_municipal_drought_assessment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
