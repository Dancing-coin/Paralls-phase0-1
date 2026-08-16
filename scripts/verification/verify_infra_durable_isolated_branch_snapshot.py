from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "explicit_snapshot_append_and_fresh_rebuild": "test_durable_isolated_branch_snapshot_rebuilds_in_fresh_authority_without_production_event",
        "missing_buffer_and_privacy_zero_write": "test_durable_isolated_branch_snapshot_rejects_missing_buffer_or_wrong_scope_without_write",
        "idempotency_and_stale_revision_zero_write": "test_durable_isolated_branch_snapshot_is_idempotent_and_rejects_stale_revision_without_write",
        "single_snapshot_zero_write": "test_durable_isolated_branch_snapshot_rejects_second_snapshot_without_write",
        "redaction_and_checkpoint_tail_replay": "test_durable_isolated_branch_snapshot_is_redacted_and_checkpoint_tail_replayable",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-durable-isolated-branch-snapshot-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-durable-isolated-branch-snapshot",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-durable-isolated-branch-snapshot-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "BranchPreviewAuthority",
        "stream": "gameplay:branch_preview:{branch_ref}",
        "event": "gameplay.branch_preview.isolated_snapshot_recorded",
        "write_path": "BranchPreviewAuthority -> GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> creator-debug outbox -> isolated branch projection",
        "limitations": [
            "Snapshots persist only redacted analysis records and never settle an Organization or Government domain fragment.",
            "Promotion, generic branch receipt/remediation, population/NPC/social truth, and production writeback remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-durable-isolated-branch-snapshot-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4M Durable Isolated Branch Snapshot Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_durable_isolated_branch_snapshot_report_json={path}")
    print(f"overall_infra_durable_isolated_branch_snapshot_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
