from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    catalog = root / "backend" / "tests" / "test_infra_governed_authority_contract_catalog.py"
    payroll = root / "backend" / "tests" / "test_infra_payroll_operating_window_closure.py"
    cases = {
        "organization_window_contract_metadata": (
            catalog,
            "test_catalog_pins_organization_operating_window_contract_metadata",
        ),
        "economy_wage_payment_contract_metadata": (
            catalog,
            "test_catalog_pins_economy_wage_payment_contract_metadata",
        ),
        "organization_window_preappend_zero_write": (
            payroll,
            "test_payroll_window_owner_contract_failure_rejects_before_append",
        ),
        "economy_wage_payment_preappend_zero_write": (
            payroll,
            "test_payroll_wage_payment_contract_failure_rejects_before_append",
        ),
        "wage_payment_scope_and_receipt": (
            payroll,
            "test_payroll_wage_payment_emits_scoped_actor_and_authority_outbox",
        ),
        "window_duplicate_and_revision_conflict": (
            payroll,
            "test_payroll_window_closure_duplicate_idempotency_replays_without_second_write",
        ),
        "full_checkpoint_tail_replay": (
            payroll,
            "test_payroll_window_closure_full_and_checkpoint_tail_replay_match",
        ),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_file, selector) in cases.items():
        log_path = verification_dir(root) / f"infra-payroll-owner-contract-catalog-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", f"{test_file}::{selector}"], root, log_path
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-payroll-owner-contract-catalog",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "evidence": evidence,
        "run_id": f"infra-payroll-owner-contract-catalog-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "limitations": [
            "The catalog is source-controlled and read-only; it cannot register or append contracts.",
            "This does not admit generic payroll policy, caller-open registration, arbitrary cross-domain settlement, or a scheduler.",
        ],
    }
    path = verification_dir(root) / "infra-payroll-owner-contract-catalog-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2R Payroll Owner-Contract Catalog Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
