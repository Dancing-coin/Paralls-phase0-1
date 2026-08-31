from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "contract_source_and_fulfillment": (
            "backend/tests/test_inf2ag_public_workshop_service_contract.py",
            "test_public_use_creates_and_fulfills_fixed_public_workshop_contract",
        ),
        "contract_zero_write_and_generic_fence": (
            "backend/tests/test_inf2ag_public_workshop_service_contract.py",
            "test_public_workshop_contract_duplicate_and_generic_paths_are_zero_write",
        ),
        "package_digest_and_activation": (
            "backend/tests/test_inf2ag_public_workshop_service_package.py",
            "test_frozen_v5_public_workshop_package_has_exact_digest_and_service_content",
        ),
        "fixed_economy_settlement_and_replay": (
            "backend/tests/test_inf2ag_public_workshop_service_exchange.py",
            "test_public_workshop_package_settles_once_with_fixed_price_and_replay",
        ),
        "price_and_duplicate_zero_write": (
            "backend/tests/test_inf2ag_public_workshop_service_exchange.py",
            "test_public_workshop_exchange_price_and_changed_duplicate_are_zero_write",
        ),
        "caller_selected_idempotency_zero_write": (
            "backend/tests/test_inf2ag_public_workshop_service_exchange.py",
            "test_public_workshop_exchange_rejects_caller_selected_idempotency_key",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (relative, selector) in cases.items():
        log_path = verification_dir(root) / f"inf2ag-public-workshop-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{root / relative}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "inf2ag-public-workshop-service-exchange",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted({path for path, _selector in cases.values()}),
        "evidence": evidence,
        "run_id": f"inf2ag-public-workshop-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "row": "committed INF-1AJ facility public use -> Contract public workshop session -> fixed Economy package exchange",
        "limitations": [
            "The package is one immutable v5 content row with fixed 12 currency:local settlement.",
            "Construction, Contract, and Economy owners retain separate events, receipts, privacy and replay readers.",
        ],
    }
    path = verification_dir(root) / "inf2ag-public-workshop-service-exchange-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2AG Public Workshop Service Exchange Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"inf2ag_public_workshop_report_json={path}")
    print(f"overall_inf2ag_public_workshop_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
