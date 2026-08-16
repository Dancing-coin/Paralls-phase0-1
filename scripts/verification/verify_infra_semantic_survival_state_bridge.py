from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_semantic_effect_lifecycle.py"
    cases = {
        "semantic_proposal_to_survival_owner_success": "test_closed_cold_proposal_delegates_to_survival_owner_and_opens_replayable_obligation",
        "overheated_row_owner_submission": "test_closed_overheated_proposal_uses_the_registered_survival_owner_row",
        "duplicate_idempotency": "test_closed_cold_proposal_replays_duplicate_without_second_owner_write",
        "altered_idempotency_payload_zero_write": "test_closed_cold_proposal_rejects_reused_key_with_changed_effect_without_writes",
        "target_revision_zero_write": "test_closed_cold_proposal_rejects_stale_survival_revision_without_writes",
        "privacy_scope_zero_write": "test_closed_cold_proposal_rejects_nonproject_privacy_without_writes",
        "unmapped_owner_zero_write": "test_closed_cold_proposal_rejects_unmapped_owner_row_without_writes",
        "checkpoint_tail_replay": "test_closed_cold_proposal_replays_through_survival_checkpoint_tail_projection",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-survival-state-bridge-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-survival-state-bridge",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-semantic-survival-state-bridge-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "SurvivalAuthority",
        "stream": "gameplay:survival:{actor_ref}",
        "events": ["gameplay.survival.state_applied", "gameplay.survival.obligation_opened"],
        "write_path": "semantic proposal -> SemanticSettlementAuthority closed bridge -> SurvivalAuthority -> GameplayCommandEnvelope -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only authority:semantic -> effect:cold_exposure -> state:cold@1 or effect:heat_exposure -> state:overheated@1 -> SurvivalAuthority is admitted.",
            "The evaluator remains proposal-only; no generic semantic owner matrix, generic state lifecycle, or direct semantic write is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-semantic-survival-state-bridge-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1B Semantic Survival State Bridge Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_semantic_survival_state_bridge_report_json={path}")
    print(f"overall_infra_semantic_survival_state_bridge_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
