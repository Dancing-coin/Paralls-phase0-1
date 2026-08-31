from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "fixed_operational_verification_and_replay": (
            "backend/tests/test_inf1ai_facility_operational_verification.py",
            "test_completed_run_commits_one_operational_verification_and_replays",
        ),
        "duplicate_and_revision_zero_write": (
            "backend/tests/test_inf1ai_facility_operational_verification.py",
            "test_operational_verification_duplicate_changed_and_stale_source_are_zero_write",
        ),
        "privacy_and_catalog_zero_write": (
            "backend/tests/test_inf1ai_facility_operational_verification.py",
            "test_operational_verification_rejects_private_source_and_catalog_mismatch",
        ),
        "construction_catalog_regression": (
            "backend/tests/test_infra_governed_authority_contract_catalog.py",
            "test_catalog_materializes_only_existing_cross_inf_owner_contracts",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"infra-construction-operational-verification-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-facility-operational-verification",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"infra-construction-operational-verification-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "committed project-visible run_finished -> existing Construction facility operational verification",
        "limitations": [
            "No Production output, Inventory custody, payment, maintenance, permit, technology, weather, social, population, compensation, or generic transform fact is written.",
            "The verification is one terminal record per facility/run and preserves the existing Construction owner/replay boundary.",
        ],
    }
    path = verification_dir(root) / "infra-construction-facility-operational-verification-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AI Construction Facility Operational Verification Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_construction_facility_operational_verification_report_json={path}")
    print(f"overall_infra_construction_facility_operational_verification_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
