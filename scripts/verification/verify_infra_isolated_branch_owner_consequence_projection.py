from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "supply_projection_zero_production_write": "test_isolated_branch_projects_supply_consequence_without_production_write",
        "inspection_projection_zero_production_write": "test_isolated_branch_projects_inspection_consequence_without_production_write",
        "rejected_fragment_has_no_projection_zero_production_write": "test_isolated_branch_does_not_project_rejected_owner_consequence",
        "owner_only_reference_redaction": "test_isolated_branch_consequence_projection_redacts_owner_only_references",
        "checkpoint_tail_branch_replay_zero_production_write": "test_isolated_branch_consequence_projection_checkpoint_tail_matches_full",
        "base_digest_zero_production_write": "test_inf4z_branch_preview_rejects_fixed_base_digest_without_production_writes",
        "unknown_profile_zero_production_write": "test_inf4z_branch_preview_rejects_unknown_candidate_profile_without_production_writes",
        "promotion_unsupported": "test_isolated_branch_consequence_projection_promotion_remains_unsupported",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-isolated-branch-owner-consequence-projection-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-isolated-branch-owner-consequence-projection",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-isolated-branch-owner-consequence-projection-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["BranchPreviewAuthority", "OrganizationAuthority", "GovernmentAuthority"],
        "write_path": "validated existing-owner fragment -> isolated redacted branch record/reducer only; no GameplayEventStore.append_batch or production outbox",
        "limitations": [
            "Only supply and inspection use closed owner-fragment semantics.",
            "The local projected facts are counterfactual branch data, not GameplayEvents, receipts or settled domain truth.",
            "Production settlement and branch promotion remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-isolated-branch-owner-consequence-projection-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4G Isolated Owner Consequence Projection Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_isolated_branch_owner_consequence_projection_report_json={path}")
    print(f"overall_infra_isolated_branch_owner_consequence_projection_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
