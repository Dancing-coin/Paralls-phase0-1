from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "registered_owner_fragment_evaluation_zero_production_write": "test_isolated_branch_evaluates_registered_owner_fragment_without_production_write",
        "owner_rejection_and_stale_zero_production_write": "test_isolated_branch_owner_fragment_rejection_and_stale_revision_are_zero_production_write",
        "checkpoint_tail_and_promotion_unsupported": "test_isolated_branch_events_rebuild_projection_and_checkpoint_tail_without_production_append",
        "base_digest_zero_production_write": "test_inf4z_branch_preview_rejects_fixed_base_digest_without_production_writes",
        "unknown_profile_zero_production_write": "test_inf4z_branch_preview_rejects_unknown_candidate_profile_without_production_writes",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-isolated-branch-owner-fragment-evaluation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-isolated-branch-owner-fragment-evaluation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-isolated-branch-owner-fragment-evaluation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["BranchPreviewAuthority", "OrganizationAuthority", "GovernmentAuthority"],
        "write_path": "frozen branch candidate -> existing owner fragment-builder validation -> isolated branch consequence record/replay; no GameplayEventStore.append_batch or production outbox",
        "limitations": [
            "Only supply and inspection use closed owner builder mappings.",
            "The generated fragment digest is an analysis artifact, not a production event, receipt or domain consequence.",
            "Promotion and all production writes remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-isolated-branch-owner-fragment-evaluation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4F Isolated Owner-Fragment Evaluation Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_isolated_branch_owner_fragment_evaluation_report_json={path}")
    print(f"overall_infra_isolated_branch_owner_fragment_evaluation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
