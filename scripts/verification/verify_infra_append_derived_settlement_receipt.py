from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    receipt_path = root / "backend" / "tests" / "test_infra_append_derived_settlement_receipt.py"
    obligation_path = root / "backend" / "tests" / "test_infra_owner_only_obligation_commit_spine.py"
    cases = {
        "committed_append_derivation": (receipt_path, "test_settlement_receipt_is_derived_from_one_committed_append_result"),
        "rejected_append_zero_write": (receipt_path, "test_settlement_receipt_preserves_rejected_append_zero_write"),
        "economy_reader_delegation": (receipt_path, "test_economy_account_receipt_delegates_to_append_derived_factory"),
        "economy_scope_privacy": (receipt_path, "test_economy_account_receipt_rejects_non_authority_scope"),
        "commerce_reader_delegation": (receipt_path, "test_commerce_receipt_delegates_to_append_derived_factory"),
        "commerce_scope_privacy": (receipt_path, "test_commerce_receipt_rejects_non_authority_scope"),
        "obligation_reader_delegation": (receipt_path, "test_obligation_receipt_delegates_to_append_derived_factory"),
        "owner_only_append_and_replay": (obligation_path, "test_plan_settle_is_zero_write_and_survival_authority_commits_planned_batch"),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for key, (path, selector) in cases.items():
        log = verification_dir(root) / f"infra-append-derived-settlement-receipt-{key}.log"
        result = run_command([python, "-m", "pytest", "-q", str(path), "-k", selector], root, log)
        checks[key] = result.returncode == 0
        logs.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-append-derived-settlement-receipt",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(receipt_path.relative_to(root)).replace("\\", "/"),
            str(obligation_path.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": logs,
        "run_id": f"infra-append-derived-settlement-receipt-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "existing owner -> SettlementPlan/owner batch -> one append_batch -> append-derived SettlementReceipt -> scoped reader",
        "limitations": ["The factory never appends and does not authorize cross-domain settlement.", "Only existing obligation, Economy-account, and Commerce receipt readers are migrated."],
    }
    target = verification_dir(root) / "infra-append-derived-settlement-receipt-report.json"
    write_json(target, report)
    write_markdown(target.with_suffix(".md"), "INF-2S Append-Derived Settlement Receipt Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(target)
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
