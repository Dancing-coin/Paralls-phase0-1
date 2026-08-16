from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "existing_owner_disposition_zero_production_write": "test_isolated_branch_projection_records_existing_owner_dispositions_without_production_writes",
        "checkpoint_tail_replay": "test_isolated_branch_owner_disposition_checkpoint_tail_matches_full_projection",
        "base_digest_zero_write": "test_inf4z_branch_preview_rejects_fixed_base_digest_without_production_writes",
        "unknown_profile_zero_write": "test_inf4z_branch_preview_rejects_unknown_candidate_profile_without_production_writes",
        "promotion_unsupported": "test_isolated_branch_events_rebuild_projection_and_checkpoint_tail_without_production_append",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-isolated-branch-owner-disposition-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-isolated-branch-owner-disposition",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-isolated-branch-owner-disposition-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "BranchPreviewAuthority isolated analysis buffer only",
        "write_path": "fixed base/calibration/identity inputs -> isolated candidate and owner-disposition records -> local projection; no GameplayEventStore.append_batch",
        "limitations": [
            "An admitted disposition records only an existing production owner mapping; it does not execute an owner fragment or domain consequence.",
            "No promotion, branch event store, population/NPC/social truth owner, SOC, GAME, P6, or P7 is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-isolated-branch-owner-disposition-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4D Isolated Branch Owner-Disposition Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_isolated_branch_owner_disposition_report_json={path}")
    print(f"overall_infra_isolated_branch_owner_disposition_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
