from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "fixed_completion_receipt_and_tail_replay": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_exact_inf3s_assessment_contract_fulfills_with_fixed_two_event_vector_and_replay",
        ),
        "source_revision_idempotency_and_policy_zero_write": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_fulfillment_duplicate_and_stale_or_forged_source_are_zero_write",
        ),
        "source_shape_and_policy_availability_zero_write": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_fulfillment_rejects_non_municipal_active_service_without_write",
        ),
        "fixed_policy_principal_zero_write": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_fulfillment_rejects_when_fixed_policy_principal_is_not_configured",
        ),
        "generic_completion_and_transition_zero_write": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_generic_contract_transition_cannot_bypass_municipal_fulfillment_row",
        ),
        "generic_creation_zero_write": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_generic_contract_creation_cannot_reserve_municipal_fulfillment_row",
        ),
        "catalog_and_descriptor_exactness": (
            "backend/tests/test_infra_governed_authority_contract_catalog.py",
            "test_catalog_materializes_only_existing_cross_inf_owner_contracts",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf3t-municipal-drought-assessment-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf3t-municipal-drought-assessment-fulfillment",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf3t-municipal-drought-assessment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "active exact INF-3S municipal assessment Contract -> fixed Contract completion and fulfilled record",
        "limitations": [
            "No payment, inventory/right, weather, Government policy, material, production, permit, social, compensation, retry, or fanout fact is written.",
            "INF-2AD settlement and INF-4U certificate remain separate owner commands after Contract fulfillment.",
        ],
    }
    path = verification_dir(root) / "inf3t-municipal-drought-assessment-fulfillment-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-3T Municipal Drought Assessment Fulfillment Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf3t_municipal_drought_assessment_report_json={path}")
    print(f"overall_inf3t_municipal_drought_assessment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
