from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_survival_dehydration_state_obligation.py"
    cases = {
        "owner_state_obligation_append": "test_dehydration_owner_row_opens_existing_survival_obligation",
        "duplicate_idempotency": "test_dehydration_owner_row_replays_duplicate_without_second_append",
        "changed_duplicate_zero_write": "test_dehydration_owner_row_rejects_changed_duplicate_without_append",
        "revision_conflict_zero_write": "test_dehydration_owner_row_rejects_stale_revision_without_append",
        "privacy_zero_write": "test_dehydration_owner_row_rejects_nonproject_privacy_without_append",
        "unmapped_pair_zero_write": "test_dehydration_owner_row_rejects_unpaired_effect_without_append",
        "checkpoint_tail_replay": "test_dehydration_expiry_settles_with_checkpoint_tail_replay",
        "scoped_outbox": "test_dehydration_owner_row_emits_project_scoped_outbox",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-survival-dehydration-state-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-survival-dehydration-state-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-survival-dehydration-state-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "SurvivalAuthority",
        "stream": "gameplay:survival:{actor_ref}",
        "events": ["gameplay.survival.state_applied", "gameplay.survival.obligation_opened", "gameplay.survival.obligation_settled"],
        "write_path": "Semantic proposal -> Survival GameplayCommandEnvelope -> GameplayEventStore.append_batch -> scoped outbox -> Survival projection/replay",
        "limitations": [
            "Only effect:dehydration_exposure -> state:dehydrated is admitted by this package.",
            "No generic effect/state owner matrix or new Survival lifecycle policy is created.",
        ],
    }
    path = verification_dir(root) / "infra-survival-dehydration-state-obligation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1E Survival Dehydration State Obligation Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_survival_dehydration_state_obligation_report_json={path}")
    print(f"overall_infra_survival_dehydration_state_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
