from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    matrix = root / "backend" / "tests" / "test_infra_semantic_state_owner_matrix.py"
    lifecycle = root / "backend" / "tests" / "test_semantic_effect_lifecycle.py"
    cases = {
        "registered_row_exactness": (matrix, "test_registered_state_owner_matrix_returns_exact_survival_row"),
        "effect_state_mismatch_zero_write_admission": (matrix, "test_registered_state_owner_matrix_rejects_effect_state_mismatch"),
        "unregistered_owner_zero_write_admission": (matrix, "test_registered_state_owner_matrix_rejects_unregistered_owner_without_registration"),
        "deterministic_registered_rows": (matrix, "test_registered_state_owner_matrix_lists_only_registered_rows_deterministically"),
        "owner_append_success": (lifecycle, "test_closed_cold_proposal_delegates_to_survival_owner_and_opens_replayable_obligation"),
        "duplicate_idempotency": (lifecycle, "test_closed_cold_proposal_replays_duplicate_without_second_owner_write"),
        "revision_conflict_zero_write": (lifecycle, "test_closed_cold_proposal_rejects_stale_survival_revision_without_writes"),
        "privacy_zero_write": (lifecycle, "test_closed_cold_proposal_rejects_nonproject_privacy_without_writes"),
        "checkpoint_tail_replay": (lifecycle, "test_closed_cold_proposal_replays_through_survival_checkpoint_tail_projection"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-state-owner-matrix-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-state-owner-matrix",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(matrix.relative_to(root)).replace("\\", "/"), str(lifecycle.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-semantic-state-owner-matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "SurvivalAuthority only",
        "registered_rows": ["state:cold/effect:cold_exposure", "state:overheated/effect:heat_exposure", "state:dehydrated/effect:dehydration_exposure"],
        "write_path": "SemanticSettlementAuthority proposal -> existing SurvivalAuthority -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> scoped projection",
        "limitations": [
            "This is a registry representation for three existing Survival rows, not a cross-domain owner matrix.",
            "No unregistered owner, stream, event family or privacy scope is admitted.",
            "Meta-rule output remains proposal-only and generic effect lifecycle remains incomplete.",
        ],
    }
    path = verification_dir(root) / "infra-semantic-state-owner-matrix-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1F Semantic State Owner Matrix Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_semantic_state_owner_matrix_report_json={path}")
    print(f"overall_infra_semantic_state_owner_matrix_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
