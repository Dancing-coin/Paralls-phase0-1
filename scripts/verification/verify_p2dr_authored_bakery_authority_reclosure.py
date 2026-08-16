from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_p2dr_authored_bakery_authority_reclosure.py"
    cases = {
        "scheduled_procurement_success": "test_p2dr_uses_existing_authored_counter_schedule_to_commit_procurement",
        "forged_or_cross_actor_schedule_zero_write": "test_p2dr_procurement_rejects_forged_or_cross_actor_schedule_without_write",
        "fixed_organization_admission_zero_write": "test_p2dr_procurement_rejects_another_organization_without_write",
        "source_privacy_zero_write": "test_p2dr_procurement_rejects_public_schedule_source_without_write",
        "procurement_exact_duplicate_and_changed_key_zero_write": "test_p2dr_procurement_duplicate_replays_but_changed_key_is_zero_write",
        "stale_schedule_revision_zero_write": "test_p2dr_procurement_rejects_stale_schedule_revision_without_write",
        "procurement_privacy_and_replay": "test_p2dr_procurement_is_scoped_and_full_checkpoint_tail_replay_matches",
        "shared_window_production_to_wage_payment": "test_p2dr_shared_window_composes_counter_procurement_and_baker_production_to_wage_payment",
        "insufficient_funds_then_overdue": "test_p2dr_insufficient_funds_is_zero_write_until_economy_records_overdue",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, selector in cases.items():
        log_path = verification_dir(root) / f"p2dr-authored-bakery-authority-reclosure-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{selector}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "p2dr-authored-bakery-authority-reclosure",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"p2dr-authored-bakery-authority-reclosure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": {
            "organization": "actor_gameplay.organization_domain",
            "construction_production": "actor_gameplay.construction_production_domain",
            "economy": "actor_gameplay.econ1_economy_domain",
        },
        "write_path": "Each owner uses GameplayCommandEnvelope or its existing owner plan, then GameplayEventStore.append_batch(), committed outbox, replay and scoped projection.",
        "limitations": [
            "This is a fixed counter procurement consumer, not generic work evidence or consumer registration.",
            "It does not create Population/NPC/social truth, a scheduler, a second store, branch promotion, or a generic cross-domain receipt.",
        ],
    }
    path = verification_dir(root) / "p2dr-authored-bakery-authority-reclosure-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "P2D-R Authored Bakery Authority Re-closure Report",
        {
            "results": [
                {"id": name, "status": "proved" if passed else "missing", "title": name}
                for name, passed in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"p2dr_authored_bakery_authority_reclosure_report_json={path}")
    print(f"overall_p2dr_authored_bakery_authority_reclosure_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
