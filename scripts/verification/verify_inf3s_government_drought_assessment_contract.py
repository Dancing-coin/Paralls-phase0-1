from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "fixed_contract_append": ("backend/tests/test_inf3s_government_drought_assessment_contract.py", "test_project_visible_government_advisory_creates_one_fixed_authority_only_assessment_contract"),
        "source_revision_and_idempotency_zero_write": ("backend/tests/test_inf3s_government_drought_assessment_contract.py", "test_foreign_or_stale_advisory_and_changed_duplicate_are_zero_write"),
        "catalog_exactness": ("backend/tests/test_infra_governed_authority_contract_catalog.py", "test_catalog_materializes_only_existing_cross_inf_owner_contracts"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf3s-government-drought-assessment-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf3s-government-drought-assessment-contract",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf3s-government-drought-assessment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "committed Government drought advisory -> fixed Contract-owned municipal assessment service contract",
        "limitations": ["This row creates no payment, completion, Economy, weather, inventory, material, Government-policy, compensation, or fanout fact.", "Service completion and INF-2AD settlement remain separate owner rows."],
    }
    path = verification_dir(root) / "inf3s-government-drought-assessment-contract-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3S Government Drought Assessment Contract Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"inf3s_government_drought_assessment_report_json={path}")
    print(f"overall_inf3s_government_drought_assessment_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
