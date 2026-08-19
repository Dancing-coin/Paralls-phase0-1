from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = root / "backend" / "tests" / "test_infra_construction_bakery_reinforcement.py"
    cases = {
        "success_receipt_projection": "test_bakery_reinforcement_appends_one_owner_event_receipt_and_projection",
        "exact_duplicate_idempotency": "test_bakery_reinforcement_exact_duplicate_replays_append_receipt_without_write",
        "changed_duplicate_zero_write": "test_bakery_reinforcement_changed_duplicate_is_zero_write",
        "source_revision_zero_write": "test_bakery_reinforcement_source_and_revision_rejections_are_zero_write",
        "owner_resolved_privacy_outbox": "test_bakery_reinforcement_resolves_privacy_and_target_kind_inside_owner",
        "durable_source_current_pins": "test_bakery_reinforcement_can_follow_repair_with_current_pins_and_preserves_condition",
        "full_checkpoint_tail_replay": "test_bakery_reinforcement_full_and_checkpoint_tail_replay_match",
        "terminal_no_compensation_fanout": "test_bakery_reinforcement_is_terminal_and_has_no_compensation_or_fanout_surface",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-construction-bakery-reinforcement-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{tests}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-construction-bakery-reinforcement",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(tests.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-construction-bakery-reinforcement-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_row": {
            "owner_ref": "actor_gameplay.construction_production_domain",
            "stream_pattern": "gameplay:construction_production:{facility_ref}",
            "event_types": ["gameplay.construction_production.facility_transformed"],
            "projection_scope": "project",
        },
        "write_path": "GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch -> ConstructionProductionAuthority.projector/outbox",
        "limitations": [
            "Only the exact committed project-visible bakery acquisition may transition to bakery_reinforced.",
            "The transition is terminal: no compensation, reversal, retry, fanout, payment, material, or generic transform semantics are admitted.",
        ],
    }
    path = verification_dir(root) / "infra-construction-bakery-reinforcement-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AF Bakery Reinforcement Report",
        {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_construction_bakery_reinforcement_report_json={path}")
    print(f"overall_infra_construction_bakery_reinforcement_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
