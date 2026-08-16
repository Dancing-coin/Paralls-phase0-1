from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    c5_tests = root / "backend" / "tests" / "test_infra_fixed_base_branch_replay_contract.py"
    existing_promotion_tests = root / "backend" / "tests" / "test_infra_organization_supply_promotion.py"
    cases = {
        "canonical_fixed_base_and_input_order": (c5_tests, "test_c5_contract_canonicalizes_fixed_base_source_and_candidate_ordering"),
        "wrong_base_zero_write": (c5_tests, "test_c5_preview_rejects_wrong_fixed_base_without_any_write"),
        "wrong_calibration_zero_write": (c5_tests, "test_c5_preview_rejects_wrong_calibration_digest_without_any_write"),
        "cross_branch_stream_zero_write": (c5_tests, "test_c5_contract_rejects_cross_branch_stream_without_any_write"),
        "privacy_scope_zero_write": (c5_tests, "test_c5_contract_rejects_privacy_scope_without_any_write"),
        "full_checkpoint_tail_projection_digest": (c5_tests, "test_c5_durable_projection_exposes_stable_contract_projection_digest"),
        "fixed_owner_admission_contract": (c5_tests, "test_c5_fixed_supply_promotion_admission_reads_matching_replay_contract"),
        "unregistered_promotion_zero_write": (c5_tests, "test_c5_unregistered_promotion_remains_zero_write"),
        "fixed_owner_production_promotion": (existing_promotion_tests, "test_organization_promotes_one_durable_supply_into_existing_production_stream"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-fixed-base-branch-replay-contract-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-fixed-base-branch-replay-contract",
        "canonical_package": "INF-C5 (INF-4)",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(c5_tests.relative_to(root)).replace("\\", "/"),
            str(existing_promotion_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": evidence,
        "run_id": f"infra-fixed-base-branch-replay-contract-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "authority:branch_preview plus existing OrganizationAuthority fixed promotion owner",
        "stream": "gameplay:branch_preview:{branch_ref}; fixed production owner stream remains gameplay:organization:{organization_ref}",
        "event_family": [
            "gameplay.branch_preview.isolated_snapshot_recorded",
            "gameplay.branch_preview.owner_consequence_applied",
            "gameplay.branch_preview.supply_admission_recorded",
            "gameplay.organization.commerce_commitment_accepted",
        ],
        "write_path": "existing owner -> GameplayCommandEnvelope/SettlementPlan -> one GameplayEventStore.append_batch -> outbox/replay -> scoped branch or production projection",
        "limitations": [
            "The contract is read-only and does not create a branch writer or promotion authority.",
            "Branch promotion remains unsupported except for the separately admitted Organization supply owner row exercised here.",
            "Generic branch settlement, generic receipt, complete group simulation, CivilizationCapability and external ingestion remain unimplemented or blocked.",
        ],
    }
    path = verification_dir(root) / "infra-fixed-base-branch-replay-contract-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-C5 (INF-4) Fixed-Base Branch Replay Contract Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_fixed_base_branch_replay_contract_report_json={path}")
    print(f"overall_infra_fixed_base_branch_replay_contract_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
