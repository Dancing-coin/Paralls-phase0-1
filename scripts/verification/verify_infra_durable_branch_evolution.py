from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_durable_branch_evolution.py"
    cases = {
        "branch_stream_append_and_projection": "test_durable_branch_evolution_appends_existing_branch_stream_and_rebuilds",
        "unsupported_or_private_zero_write": "test_durable_branch_evolution_rejects_scope_or_missing_step_without_write",
        "idempotency_and_revision_zero_write": "test_durable_branch_evolution_is_idempotent_and_revisioned",
        "changed_duplicate_zero_write": "test_durable_branch_evolution_rejects_changed_duplicate_without_write",
        "fresh_checkpoint_tail_replay": "test_durable_branch_evolution_checkpoint_tail_matches_fresh_replay",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-durable-branch-evolution-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-durable-branch-evolution",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-durable-branch-evolution-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "authority:branch_preview",
        "stream": "gameplay:branch_preview:{branch_ref}",
        "event_family": ["gameplay.branch_preview.isolated_snapshot_recorded", "gameplay.branch_preview.owner_consequence_applied"],
        "write_path": "BranchPreviewAuthority -> GameplayCommandEnvelope/SettlementPlan -> one GameplayEventStore.append_batch -> creator_debug outbox -> durable isolated branch projection",
        "limitations": [
            "Only one fixed redacted owner-consequence evolution step is admitted per evaluated intent.",
            "No production truth, generic branch writer, branch-domain settlement receipt, generic promotion, CivilizationCapability, SOC, GAME, P6, or P7 is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-durable-branch-evolution-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4P Durable Branch Evolution Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_durable_branch_evolution_report_json={path}")
    print(f"overall_infra_durable_branch_evolution_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
