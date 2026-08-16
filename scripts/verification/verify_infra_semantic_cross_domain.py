from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_semantic_cross_domain.py"
    cases = {
        "production_owner_fragment_success_and_outbox": "test_semantic_production_finish_settles_only_through_owner_fragment_and_outbox",
        "owner_decline_zero_write": "test_semantic_production_finish_owner_decline_is_zero_write",
        "duplicate_idempotency": "test_semantic_production_finish_duplicate_is_idempotent",
        "revision_conflict_zero_write": "test_semantic_production_finish_revision_conflict_is_zero_write",
        "private_proposal_zero_write": "test_semantic_production_finish_private_evidence_is_zero_write",
        "full_and_checkpoint_tail_replay": "test_semantic_production_finish_checkpoint_tail_replay_matches_full",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-cross-domain-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-cross-domain",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-semantic-cross-domain-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": [
            "backend/app/gameplay/semantic_authority.py",
            "backend/app/gameplay/construction_production_runtime.py",
        ],
        "write_path": "SemanticSettlementAuthority -> owner-authorized production fragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only effect:production_due_finish is admitted.",
            "Economy, survival, ecology, generic rule language, retry, and compensation remain unadmitted.",
        ],
    }
    path = verification_dir(root) / "infra-semantic-cross-domain-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1R Semantic Cross-Domain Report",
        {
            "results": [
                {"id": name, "status": "proved" if status else "missing", "title": name}
                for name, status in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_semantic_cross_domain_report_json={path}")
    print(f"overall_infra_semantic_cross_domain_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
