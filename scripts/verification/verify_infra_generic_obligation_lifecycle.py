from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_generic_obligation_lifecycle.py"
    cases = {
        "two_owner_open_projection": "test_lifecycle_projection_rebuilds_open_obligations_for_two_registered_owners",
        "due_is_read_only": "test_lifecycle_projection_derives_due_without_writing_a_second_lifecycle_fact",
        "canonical_status_contract": "test_scheduled_obligation_accepts_canonical_generic_lifecycle_statuses",
        "survival_settled_projection": "test_lifecycle_projection_rebuilds_survival_settled_terminal_fact",
        "bounded_survival_retry": "test_registered_survival_retry_reschedules_open_obligation_with_bounded_attempts",
        "retry_reenters_shared_clock_and_settlement": "test_retry_lifecycle_reenters_shared_clock_and_owner_settlement",
        "survival_compensation": "test_registered_survival_compensation_restores_only_a_settled_state",
        "unregistered_and_exhausted_zero_write": "test_unregistered_compensation_and_retry_exhaustion_are_zero_write",
        "retry_revision_conflict_zero_write": "test_survival_retry_revision_conflict_is_zero_write",
        "compensation_idempotency_privacy_replay": "test_survival_compensation_is_idempotent_private_and_checkpoint_replayable",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-generic-obligation-lifecycle-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-generic-obligation-lifecycle",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-generic-obligation-lifecycle-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ConstructionProductionAuthority", "SurvivalAuthority"],
        "write_path": "existing owner fragment -> ObligationSettlementCoordinator -> GameplayEventStore.append_batch -> project outbox/replay/scoped receipt",
        "limitations": [
            "Only Survival state:cold@1 admits retry and compensation owner events.",
            "Construction retry/compensation, ecology lifecycle, and universal domain policies remain unimplemented or zero-write rejected.",
            "This profile does not prove activation pending merge. Separate INF-2B evidence admits only released survival_state_expiry for state:cold@1; generic activation-obligation binding remains unimplemented.",
            "The lifecycle projection is read-only and does not create an obligation store or scheduler.",
        ],
    }
    path = verification_dir(root) / "infra-generic-obligation-lifecycle-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2A Generic Obligation Lifecycle Report", {"results": [{"id": name, "status": "proved" if passed else "missing", "title": name} for name, passed in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_generic_obligation_lifecycle_report_json={path}")
    print(f"overall_infra_generic_obligation_lifecycle_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
