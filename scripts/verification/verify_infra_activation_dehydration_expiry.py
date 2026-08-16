from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_activation_dehydration_expiry.py"
    cases = {
        "released_pending_to_survival_fragment": "test_released_dehydration_pending_settles_through_existing_survival_fragment",
        "duplicate_idempotency": "test_released_dehydration_pending_replays_duplicate_without_second_target_write",
        "changed_duplicate_zero_write": "test_dehydration_pending_rejects_changed_duplicate_without_activation_append",
        "released_changed_duplicate_zero_write": "test_released_dehydration_pending_rejects_changed_duplicate_without_second_target_write",
        "revision_conflict_zero_write": "test_released_dehydration_pending_rejects_changed_obligation_without_target_write",
        "privacy_zero_write": "test_released_dehydration_pending_rejects_nonproject_privacy_without_target_write",
        "unregistered_state_zero_write": "test_released_dehydration_pending_rejects_unregistered_state_without_target_write",
        "terminal_obligation_zero_write": "test_released_dehydration_pending_rejects_terminal_obligation_without_target_write",
        "checkpoint_tail_replay": "test_released_dehydration_pending_checkpoint_tail_replay_matches_full",
        "separate_append_receipts": "test_dehydration_release_and_survival_settlement_have_separate_append_receipts",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-activation-dehydration-expiry-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-activation-dehydration-expiry",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-activation-dehydration-expiry-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "SurvivalAuthority"],
        "activation_stream": "population:{world_ref}",
        "survival_stream": "gameplay:survival:{actor_ref}",
        "write_path": "activation pending/release append -> event-derived pending/lifecycle projections -> Survival owner fragment -> coordinator append -> outbox/replay/scoped projection",
        "receipt_boundary": "activation release and Survival settlement are distinct append-derived receipts",
        "limitations": [
            "Only released survival_state_expiry for state:dehydrated@1 is admitted by INF-2E.",
            "The allowed state set remains closed; no generic activation-obligation binding or cross-stream atomic receipt is created.",
        ],
    }
    path = verification_dir(root) / "infra-activation-dehydration-expiry-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2E Activation Dehydration Expiry Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_activation_dehydration_expiry_report_json={path}")
    print(f"overall_infra_activation_dehydration_expiry_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
