from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "fixed_certificate_grant_and_tail_replay": ("backend/tests/test_inf4u_municipal_drought_assessment_certificate.py", "test_completed_municipal_assessment_grants_one_fixed_certificate_title"),
        "zero_write_rejections": ("backend/tests/test_inf4u_municipal_drought_assessment_certificate.py", "test_incomplete_or_changed_certificate_request_is_zero_write"),
        "generic_initial_title_zero_write": ("backend/tests/test_inf4u_municipal_drought_assessment_certificate.py", "test_generic_initial_title_cannot_reserve_municipal_certificate_identity"),
        "generic_transfer_zero_write": ("backend/tests/test_inf4u_municipal_drought_assessment_certificate.py", "test_generic_transfer_cannot_move_municipal_certificate_title"),
        "package_exchange_fragment_zero_write": ("backend/tests/test_inf4u_municipal_drought_assessment_certificate.py", "test_package_exchange_fragment_cannot_transfer_municipal_certificate_title"),
        "ownership_regression": ("backend/tests/test_ownership_runtime.py", "test_initial_title_and_independent_transfer_are_event_derived"),
        "catalog_exactness": ("backend/tests/test_infra_governed_authority_contract_catalog.py", "test_catalog_materializes_only_existing_cross_inf_owner_contracts"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf4u-municipal-drought-certificate-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf4u-municipal-drought-assessment-certificate",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf4u-municipal-drought-certificate-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "completed fixed municipal assessment contract -> exact Ownership certificate initial title",
        "limitations": ["No transfer, payment, inspection result, reputation, population, material, inventory, compensation or fanout is written.", "The certificate is an Ownership title only; service completion and Economy settlement remain separate rows."],
    }
    path = verification_dir(root) / "inf4u-municipal-drought-assessment-certificate-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4U Municipal Drought Assessment Certificate Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"inf4u_municipal_drought_certificate_report_json={path}")
    print(f"overall_inf4u_municipal_drought_certificate_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
