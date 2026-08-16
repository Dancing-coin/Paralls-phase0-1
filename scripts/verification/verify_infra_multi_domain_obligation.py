from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_multi_domain_obligation.py"
    cases = {
        "clock_owner_fragment_event_spine": "test_production_due_policy_uses_clock_then_owner_fragment_then_event_spine",
        "duplicate_idempotency": "test_production_due_policy_duplicate_replays_without_second_write",
        "revision_conflict_zero_write": "test_production_due_policy_revision_conflict_is_zero_write",
        "cancelled_zero_write": "test_production_due_policy_cancelled_obligation_is_zero_write",
        "retry_compensation_unsupported_zero_write": "test_unregistered_retry_and_compensation_are_zero_write",
        "privacy_and_checkpoint_tail_replay": "test_production_due_policy_public_receipt_is_filtered_and_replay_matches",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-multi-domain-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-multi-domain-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-multi-domain-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/construction_production_runtime.py", "backend/app/world_runtime/obligations.py"],
        "write_path": "SimulationClock caller -> construction owner fragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped receipt",
        "limitations": ["Only construction production completion is admitted.", "Retry, compensation, and ecology remain unsupported with zero writes."],
    }
    path = verification_dir(root) / "infra-multi-domain-obligation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2R Multi-Domain Obligation Report", {"results": [{"id": name, "status": "proved" if status else "missing", "title": name} for name, status in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_multi_domain_obligation_report_json={path}")
    print(f"overall_infra_multi_domain_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
