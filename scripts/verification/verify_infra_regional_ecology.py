from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_regional_ecology.py"
    cases = {
        "committed_source_proposal_one_finish_append": "test_committed_frost_proposal_has_no_target_and_construction_commits_one_finish_event",
        "committed_outbox_scoped_projection": "test_frost_finish_writes_one_scoped_outbox_entry",
        "duplicate_idempotency": "test_frost_finish_duplicate_is_idempotent_without_second_production_write",
        "changed_proposal_zero_write": "test_frost_finish_changed_proposal_after_commit_is_zero_write_rejected",
        "source_revision_zero_write": "test_frost_finish_source_revision_conflict_is_zero_write",
        "target_not_due_zero_write": "test_frost_finish_not_due_target_is_zero_write",
        "target_missing_zero_write": "test_frost_finish_missing_target_is_zero_write",
        "privacy_scope_zero_write": "test_frost_finish_private_scope_is_zero_write",
        "retry_zero_write": "test_frost_finish_retry_is_zero_write",
        "compensation_zero_write": "test_frost_finish_compensation_is_zero_write",
        "public_projection_redaction": "test_frost_finish_public_projection_redacts_provenance",
        "authority_projection_provenance": "test_frost_finish_authority_projection_retains_provenance",
        "full_checkpoint_tail_replay": "test_frost_finish_checkpoint_tail_replay_is_deterministic",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-regional-ecology-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-regional-ecology",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-regional-ecology-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["backend/app/gameplay/ecology_runtime.py", "backend/app/gameplay/construction_production_runtime.py"],
        "write_path": "committed ecology source -> ConstructionProductionAuthority fragment -> GameplayEventStore.append_batch -> outbox/replay/scoped projection",
        "limitations": ["Only the fixed frost-to-due-production-finish edge is admitted.", "No ecology retry or compensation is implemented."],
    }
    path = verification_dir(root) / "infra-regional-ecology-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3R Regional Ecology Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_regional_ecology_report_json={path}")
    print(f"overall_infra_regional_ecology_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
