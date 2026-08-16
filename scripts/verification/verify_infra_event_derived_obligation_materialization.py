from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_file = root / "backend" / "tests" / "test_infra_event_derived_scheduled_obligation_materialization.py"
    cases = {
        "two_owner_materialization": "test_event_derived_view_materializes_scheduled_obligations_for_two_existing_owners",
        "bounded_due_zero_write": "test_event_derived_due_materialization_is_bounded_and_does_not_write",
        "checkpoint_tail_equivalence": "test_event_derived_materialization_reconstructs_from_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for name, selector in cases.items():
        log = verification_dir(root) / f"infra-event-derived-obligation-materialization-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_file), "-k", selector], root, log)
        checks[name] = result.returncode == 0
        evidence.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-event-derived-obligation-materialization",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_file.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-event-derived-obligation-materialization-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "write_path": "read-only lifecycle projection -> ScheduledObligation input -> existing owner fragment -> GameplayEventStore.append_batch",
        "limitations": [
            "Registered owner rows only; caller-open policy registration remains rejected.",
            "Materialization never appends, advances a clock, selects an owner, or creates a receipt.",
        ],
    }
    path = verification_dir(root) / "infra-event-derived-obligation-materialization-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2W Event-Derived Obligation Materialization Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()]},
        "overall_passed",
    )
    print(f"infra_event_derived_obligation_materialization_report_json={path}")
    print(f"overall_infra_event_derived_obligation_materialization_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
