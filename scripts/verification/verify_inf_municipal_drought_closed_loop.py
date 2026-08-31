from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "admitted_owner_chain": (
            "backend/tests/test_inf_municipal_drought_closed_loop.py",
            "test_municipal_drought_assessment_closed_loop_uses_only_admitted_owner_rows",
        ),
        "contract_fulfillment_zero_write": (
            "backend/tests/test_inf3t_municipal_drought_assessment_fulfillment.py",
            "test_fulfillment_duplicate_and_stale_or_forged_source_are_zero_write",
        ),
        "economy_settlement_zero_write": (
            "backend/tests/test_inf2ad_municipal_drought_assessment_exchange.py",
            "test_wrong_service_evidence_and_changed_or_price_mismatched_duplicate_are_zero_write",
        ),
        "ownership_certificate_zero_write": (
            "backend/tests/test_inf4u_municipal_drought_assessment_certificate.py",
            "test_incomplete_or_changed_certificate_request_is_zero_write",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf-municipal-drought-closed-loop-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf-municipal-drought-closed-loop",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf-municipal-drought-closed-loop-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "chain": [
            "project-visible drought weather-front -> Government advisory",
            "Government advisory -> Contract municipal assessment admission",
            "active exact Contract -> Contract completion/fulfilled pair",
            "fulfilled exact Contract -> Economy fixed settlement",
            "fulfilled exact Contract -> Ownership certificate title",
            "exact certificate -> Government authority-only assessment acknowledgment",
        ],
        "limitations": [
            "Each step has an independent append receipt and no combined cross-owner receipt.",
            "The proof does not admit generic payment, contract completion, certificate, fanout, router, registry, or a new owner.",
        ],
    }
    path = verification_dir(root) / "inf-municipal-drought-closed-loop-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF Municipal Drought Closed Loop Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf_municipal_drought_closed_loop_report_json={path}")
    print(f"overall_inf_municipal_drought_closed_loop_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
