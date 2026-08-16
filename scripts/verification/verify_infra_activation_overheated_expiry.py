from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_activation_overheated_expiry.py"
    cases = {
        "released_pending_to_survival_fragment": "test_released_overheated_pending_settles_through_existing_survival_fragment",
        "exact_duplicate_no_second_target_write": "test_released_overheated_pending_replays_exact_duplicate_without_second_target_write",
        "changed_duplicate_zero_target_write": "test_released_overheated_pending_rejects_changed_duplicate_without_second_target_write",
        "changed_pending_duplicate_zero_activation_write": "test_overheated_pending_rejects_changed_pending_duplicate_without_activation_write",
        "target_revision_conflict_zero_target_write": "test_released_overheated_pending_rejects_target_revision_conflict_without_target_write",
        "privacy_zero_target_write": "test_released_overheated_pending_rejects_nonproject_privacy_without_target_write",
        "unsupported_state_zero_target_write": "test_released_overheated_pending_rejects_unsupported_state_without_target_write",
        "terminal_obligation_zero_target_write": "test_released_overheated_pending_rejects_terminal_obligation_without_target_write",
        "full_checkpoint_tail_replay": "test_released_overheated_pending_full_and_checkpoint_tail_replay_match",
        "distinct_activation_survival_receipts": "test_overheated_release_and_survival_settlement_have_distinct_append_receipts",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-activation-overheated-expiry-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", str(test_path), "-k", test_name],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-activation-overheated-expiry",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-activation-overheated-expiry-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "SurvivalAuthority"],
        "activation_stream": "population:{world_ref}",
        "survival_stream": "gameplay:survival:{actor_ref}",
        "write_path": "activation pending/release append -> event-derived pending/lifecycle projections -> Survival owner fragment -> coordinator append -> outbox/replay/scoped projection",
        "receipt_boundary": "activation release and Survival settlement are distinct append-derived receipts",
        "limitations": [
            "Only released survival_state_expiry for state:overheated@1 is admitted by INF-2F.",
            "Cold and dehydrated remain existing named rows; every other state remains rejected.",
        ],
    }
    path = verification_dir(root) / "infra-activation-overheated-expiry-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2F Activation Overheated Expiry Report",
        {
            "results": [
                {
                    "id": key,
                    "status": "proved" if value else "missing",
                    "title": key,
                }
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_activation_overheated_expiry_report_json={path}")
    print(f"overall_infra_activation_overheated_expiry_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
