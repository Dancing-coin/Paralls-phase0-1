from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "fixed_authority_acknowledgment_and_project_non_widening": (
            "backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py",
            "test_exact_municipal_certificate_acknowledges_only_authority_government_view",
        ),
        "duplicate_and_certificate_zero_write": (
            "backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py",
            "test_acknowledgment_duplicate_changed_and_forged_certificate_are_zero_write",
        ),
        "private_and_stale_source_zero_write": (
            "backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py",
            "test_acknowledgment_rejects_private_or_stale_certificate_before_append",
        ),
        "stale_target_head_zero_write": (
            "backend/tests/test_inf3u_municipal_certificate_government_acknowledgment.py",
            "test_acknowledgment_rejects_stale_government_head_before_append",
        ),
        "catalog_exactness": (
            "backend/tests/test_infra_governed_authority_contract_catalog.py",
            "test_catalog_materializes_only_existing_cross_inf_owner_contracts",
        ),
        "project_presentation_regression": (
            "backend/tests/test_infra_weather_front_government_drought_advisory_presentation.py",
            "test_foreign_scope_wrong_outbox_and_disconnected_session_are_zero_leak",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf3u-municipal-certificate-acknowledgment-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf3u-municipal-certificate-government-acknowledgment",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf3u-municipal-certificate-acknowledgment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "exact authority-only INF-4U certificate -> existing Government advisory assessment acknowledgment",
        "limitations": [
            "No project-visible advisory change, payment, restriction, permit, material, inventory, production, compensation, fanout, or generic Government lifecycle is written.",
            "Certificate issuance, Economy settlement, and Government acknowledgment retain independent owner commands and receipts.",
        ],
    }
    path = verification_dir(root) / "inf3u-municipal-certificate-government-acknowledgment-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3U Municipal Certificate Government Acknowledgment Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf3u_municipal_certificate_acknowledgment_report_json={path}")
    print(f"overall_inf3u_municipal_certificate_acknowledgment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
