from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_semantic_registered_state_owner_dispatch.py"
    cases = {
        "survival_dispatch": "test_registered_state_dispatch_routes_survival_to_existing_owner",
        "registered_owner_matrix": "test_registered_state_owner_matrix_contains_exact_seven_apply_rows",
        "construction_dispatch": "test_registered_state_dispatch_routes_construction_to_existing_owner",
        "unknown_route_zero_write": "test_registered_state_dispatch_rejects_unknown_row_without_write",
        "route_mismatch_zero_write": "test_registered_state_dispatch_rejects_wrong_route_without_write",
        "duplicate_idempotency": "test_registered_state_dispatch_preserves_survival_duplicate_idempotency",
        "revision_privacy_zero_write": "test_registered_state_dispatch_preserves_survival_revision_and_privacy_zero_write",
        "direct_helper_stale_vector_zero_write": "test_direct_survival_helper_rejects_stale_semantic_vector_without_write",
        "noncanonical_survival_definition_zero_write": "test_registered_survival_dispatch_rejects_noncanonical_state_definition_without_write",
        "construction_checkpoint_tail_replay": "test_registered_construction_dispatch_replays_full_and_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-semantic-registered-state-owner-dispatch-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-semantic-registered-state-owner-dispatch",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-semantic-registered-state-owner-dispatch-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "registered_rows": [
            "state:cold/effect:cold_exposure -> SurvivalAuthority",
            "state:overheated/effect:heat_exposure -> SurvivalAuthority",
            "state:dehydrated/effect:dehydration_exposure -> SurvivalAuthority",
            "state:maintenance_due/effect:maintenance_required -> ConstructionProductionAuthority",
        ],
        "write_path": "closed registry route -> existing owner adapter -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> scoped projection/replay",
        "limitations": [
            "The route is a closed adapter registry, not generic caller-selected owner dispatch.",
            "No new owner, lifecycle policy, scheduler, clock, event store, or cross-stream receipt is admitted.",
            "Generic additional effect/state lifecycle rows remain blocked by missing approved owner/event-family/receipt mappings (INF-1I).",
        ],
    }
    path = verification_dir(root) / "infra-semantic-registered-state-owner-dispatch-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1H Registered State Owner Dispatch Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_semantic_registered_state_owner_dispatch_report_json={path}")
    print(f"overall_infra_semantic_registered_state_owner_dispatch_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
