from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_activation_survival_expiry.py"
    cases = {
        "released_pending_to_existing_survival_fragment": "test_released_survival_expiry_pending_settles_only_through_existing_survival_fragment",
        "duplicate_idempotency": "test_released_survival_expiry_pending_replays_duplicate_without_second_write",
        "revision_conflict_zero_write": "test_released_survival_expiry_pending_rejects_changed_survival_revision_without_writes",
        "privacy_zero_write": "test_released_survival_expiry_pending_rejects_nonproject_privacy_without_target_write",
        "terminal_obligation_zero_write": "test_released_survival_expiry_pending_rejects_terminal_obligation_without_writes",
        "checkpoint_tail_replay": "test_released_survival_expiry_pending_checkpoint_tail_replay_matches_full",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-activation-survival-expiry-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-activation-survival-expiry",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-activation-survival-expiry-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "SurvivalAuthority"],
        "activation_stream": "population:{world_ref}",
        "survival_stream": "gameplay:survival:{actor_ref}",
        "write_path": "activation pending/release append -> event-derived pending/lifecycle projections -> Survival owner fragment -> coordinator append -> outbox/replay/scoped projection",
        "receipt_boundary": "activation receipt and Survival SettlementReceipt are separate append-derived receipts",
        "limitations": [
            "Only released survival_state_expiry for state:cold@1 is admitted.",
            "No generic activation-obligation binding, two-stream atomic receipt, new scheduler/store/owner, economy policy, branch promotion, SOC, GAME, P6, or P7 is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-activation-survival-expiry-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2B Activation Survival Expiry Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_activation_survival_expiry_report_json={path}")
    print(f"overall_infra_activation_survival_expiry_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
