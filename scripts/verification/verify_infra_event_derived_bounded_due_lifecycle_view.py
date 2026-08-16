from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests"
    cases = {
        "cross_owner_bounded_due": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_time_view_marks_only_the_bounded_cross_owner_due_prefix",
        ),
        "checkpoint_tail_replay": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_time_view_checkpoint_tail_replay_matches_full_replay",
        ),
        "materialized_checkpoint_zero_write": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_time_view_rejects_materialized_due_checkpoint_without_write",
        ),
        "terminal_preservation": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_projection_rebuilds_survival_settled_terminal_fact",
        ),
        "privacy_scope": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_time_view_preserves_registered_privacy_scope",
        ),
        "invalid_budget_zero_write": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_time_view_rejects_invalid_budget_without_write",
        ),
        "invalid_tick_zero_write": (
            "test_infra_generic_obligation_lifecycle.py",
            "test_lifecycle_time_view_rejects_invalid_tick_without_write",
        ),
        "closed_registration_zero_write": (
            "test_infra_closed_lifecycle_registration_admission.py",
            "test_unknown_policy_and_forged_registration_are_zero_write_rejected",
        ),
        "owner_duplicate_predecessor": (
            "test_infra_owner_only_obligation_commit_spine.py",
            "test_plan_settle_is_zero_write_and_survival_authority_commits_planned_batch",
        ),
        "owner_revision_conflict_predecessor": (
            "test_infra_economy_scheduled_transfer_obligation.py",
            "test_economy_scheduled_transfer_due_rejects_stale_revision_without_write",
        ),
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    focused_files: set[str] = set()
    for check, (filename, selector) in cases.items():
        test_path = tests / filename
        log_path = verification_dir(root) / f"infra-event-derived-bounded-due-lifecycle-view-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", str(test_path), "-k", selector],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
        focused_files.add(str(test_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-event-derived-bounded-due-lifecycle-view",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": sorted(focused_files),
        "evidence": logs,
        "run_id": f"infra-event-derived-bounded-due-lifecycle-view-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": [
            "ConstructionProductionAuthority",
            "SurvivalAuthority",
            "EcologyHazardAuthority",
            "EconomyAuthority",
            "EconomyAuthorityService",
        ],
        "write_path": "reader only; due records require an existing owner -> owner batch -> GameplayEventStore.append_batch() path to settle",
        "limitations": [
            "The lifecycle view never appends, creates a receipt, selects an owner, or advances a clock.",
            "Only immutable registrations may enter the view; caller-open policies and arbitrary cross-domain settlement remain unsupported.",
        ],
    }
    path = verification_dir(root) / "infra-event-derived-bounded-due-lifecycle-view-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2T Event-Derived Bounded Due Lifecycle View Report",
        {
            "results": [
                {"id": name, "status": "proved" if passed else "missing", "title": name}
                for name, passed in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_event_derived_bounded_due_lifecycle_view_report_json={path}")
    print(f"overall_infra_event_derived_bounded_due_lifecycle_view_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
