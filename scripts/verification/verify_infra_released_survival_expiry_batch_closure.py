from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_activation_survival_expiry.py"
    cases = {
        "released_pending_to_existing_survival_owner": "test_released_survival_expiry_pending_settles_only_through_existing_survival_fragment",
        "append_derived_receipt_boundary": "test_released_survival_expiry_pending_keeps_activation_and_survival_receipts_separate",
        "duplicate_idempotency": "test_released_survival_expiry_pending_replays_duplicate_without_second_write",
        "revision_conflict_zero_write": "test_released_survival_expiry_pending_rejects_changed_survival_revision_without_writes",
        "privacy_zero_write": "test_released_survival_expiry_pending_rejects_nonproject_privacy_without_target_write",
        "terminal_obligation_zero_write": "test_released_survival_expiry_pending_rejects_terminal_obligation_without_writes",
        "checkpoint_tail_replay": "test_released_survival_expiry_pending_checkpoint_tail_replay_matches_full",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-released-survival-expiry-batch-closure-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-released-survival-expiry-batch-closure",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-released-survival-expiry-batch-closure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "SurvivalAuthority"],
        "activation_stream": "population:{world_ref}",
        "survival_stream": "gameplay:survival:{profile_ref}",
        "write_path": "released activation pending -> read-only activation/lifecycle projection -> SurvivalAuthority fragment -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay -> scoped projection",
        "receipt_boundary": "The returned Survival SettlementReceipt derives from only the Survival append result; activation records retain their own prior append-derived receipts.",
        "limitations": [
            "Only the pre-registered survival_state_expiry bindings are admitted; this profile exercises the existing cold row and does not open caller-selected state, owner, stream or policy input.",
            "No generic population merge, cross-stream atomic receipt, scheduler, branch promotion, population truth owner, NPC/social truth store, SOC, GAME, P6, or P7 work is admitted."
        ]
    }
    path = verification_dir(root) / "infra-released-survival-expiry-batch-closure-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4AB Released Survival Expiry Batch Closure Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_released_survival_expiry_batch_closure_report_json={path}")
    print(f"overall_infra_released_survival_expiry_batch_closure_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
