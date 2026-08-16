from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_survival_heat_state_obligation.py"
    cases = {
        "owner_open": "test_overheated_owner_row_opens_existing_survival_obligation",
        "idempotency": "test_overheated_owner_row_is_idempotent",
        "revision_conflict_zero_write": "test_overheated_owner_row_rejects_stale_revision_without_writes",
        "privacy_zero_write": "test_overheated_owner_row_rejects_nonproject_privacy_without_writes",
        "unpaired_effect_zero_write": "test_overheated_owner_row_rejects_unpaired_effect_without_writes",
        "expiry_settlement_checkpoint_tail_replay": "test_overheated_expiry_settles_and_replays_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-survival-heat-state-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-survival-heat-state-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-survival-heat-state-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner_row": {
            "effect_ref": "effect:heat_exposure",
            "state_ref": "state:overheated",
            "owner": "actor_gameplay.survival_domain",
            "stream": "gameplay:survival:{actor_ref}",
            "event_family": ["gameplay.survival.state_*", "gameplay.survival.obligation_*"],
            "privacy": "project",
        },
        "write_path": "SemanticSettlementAuthority proposal -> existing SurvivalAuthority GameplayCommandEnvelope -> existing append_batch/outbox/replay/scoped projection",
        "limitations": [
            "This is a second explicit Survival row, not generic effect/state ownership or a cross-owner lifecycle.",
            "No new scheduler, state store, population/NPC/social owner, or P6/P7 work is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-survival-heat-state-obligation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1D Survival Heat State Obligation Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_survival_heat_state_obligation_report_json={path}")
    print(f"overall_infra_survival_heat_state_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
