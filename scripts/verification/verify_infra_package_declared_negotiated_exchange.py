from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_package_declared_negotiated_exchange.py"
    selectors = {
        "inventory_success": f"{test_path}::test_package_declared_exchange_commits_one_fixed_owner_vector_for_each_admitted_source_mode[inventory_success]",
        "ownership_success": f"{test_path}::test_package_declared_exchange_commits_one_fixed_owner_vector_for_each_admitted_source_mode[ownership_success]",
        "completed_service_success": f"{test_path}::test_package_declared_exchange_commits_one_fixed_owner_vector_for_each_admitted_source_mode[completed_service_success]",
        "price_zero_write": f"{test_path}::test_package_exchange_rejects_price_outside_fixed_policy_without_writes",
        "source_zero_write": f"{test_path}::test_package_exchange_rejects_ambiguous_package_source_without_writes",
        "capability_zero_write": f"{test_path}::test_package_exchange_rejects_capability_mismatch_without_writes",
        "package_revision_zero_write": f"{test_path}::test_package_exchange_rejects_inactive_package_revision_without_writes",
        "receipt_privacy": f"{test_path}::test_package_exchange_receipt_is_authority_only_and_append_derived",
        "full_replay": f"{test_path}::test_package_exchange_projection_is_authority_only_and_full_replay_is_fixed",
        "checkpoint_tail_replay": f"{test_path}::test_package_exchange_checkpoint_tail_replay_matches_full_replay",
        "idempotency": f"{test_path}::test_package_exchange_exact_duplicate_replays_and_changed_duplicate_is_zero_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, nodeid in selectors.items():
        log_path = verification_dir(root) / f"infra-package-declared-negotiated-exchange-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", nodeid], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-package-declared-negotiated-exchange",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-package-declared-negotiated-exchange-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": [
            "InventoryAuthorityService",
            "OwnershipAuthorityService",
            "ContractAuthorityService",
            "EconomyAuthorityService",
        ],
        "contract_ref": "inf:package-declared-negotiated-exchange@1",
        "economic_outcome_id": "package_declared_negotiated_exchange@1",
        "write_path": "PackageDeclaredNegotiatedExchangeIntentV1 -> EconomyAuthorityService -> AppendDerivedSettlementRecipe.from_fragments() -> GameplayEventStore.append_batch() with fixed owner-authorized fragments",
        "receipt_boundary": "Only the one append-derived authority receipt is exposed; public and project receipt/projection scopes remain rejected.",
        "limitations": [
            "Only one immutable package-declared item, right, or completed service exchange is admitted.",
            "This does not admit generic payment, transfer, treasury, market pricing, router, registry, coordinator, compensation, or any new truth owner.",
        ],
    }
    path = verification_dir(root) / "infra-package-declared-negotiated-exchange-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2AC Package-Declared Negotiated Exchange Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_package_declared_negotiated_exchange_report_json={path}")
    print(f"overall_infra_package_declared_negotiated_exchange_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
