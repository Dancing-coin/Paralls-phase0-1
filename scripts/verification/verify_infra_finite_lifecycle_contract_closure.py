from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    contract_tests = root / "backend" / "tests" / "test_infra_finite_lifecycle_contract_closure.py"
    survival_tests = root / "backend" / "tests" / "test_infra_semantic_survival_state_action.py"
    construction_tests = root / "backend" / "tests" / "test_infra_construction_maintenance_state_action.py"
    ecology_tests = root / "backend" / "tests" / "test_infra_ecology_frost_state_obligation.py"
    economy_tests = root / "backend" / "tests" / "test_infra_semantic_economy_wage_obligation.py"
    cases = {
        "six_contract_shape": (contract_tests, "test_finite_lifecycle_contract_reader_materializes_only_existing_owner_rows"),
        "unknown_contract_zero_write": (contract_tests, "test_finite_lifecycle_contract_reader_rejects_unknown_rows"),
        "closed_action_admission": (contract_tests, "test_finite_lifecycle_contract_reader_fixes_owner_actions_and_terminal_event_families"),
        "fixed_metadata": (contract_tests, "test_finite_lifecycle_contract_reader_exposes_fixed_projection_revision_idempotency_and_replay_metadata"),
        "survival_action_owner_fence": (survival_tests, "test_semantic_survival_state_action_rejects_wrong_owner_without_write"),
        "survival_checkpoint_tail_replay": (survival_tests, "test_semantic_survival_state_action_replays_full_and_checkpoint_tail"),
        "construction_action_contract_fence": (construction_tests, "test_semantic_construction_maintenance_dispel_uses_closed_state_contract_before_fragment_write"),
        "construction_checkpoint_tail_replay": (construction_tests, "test_semantic_construction_maintenance_dispel_checkpoint_tail_replay_matches_full_projection"),
        "ecology_contract_fence": (ecology_tests, "test_ecology_frost_crop_state_rejects_forged_shared_owner_contract_without_write"),
        "ecology_checkpoint_tail_replay": (ecology_tests, "test_ecology_frost_crop_state_checkpoint_tail_replay_matches_full_replay"),
        "economy_owner_fence": (economy_tests, "test_semantic_wage_effect_rejects_wrong_owner_without_write"),
        "economy_checkpoint_tail_replay": (economy_tests, "test_semantic_wage_effect_lifecycle_replays_full_and_checkpoint_tail"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-finite-lifecycle-contract-closure-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", f"{test_path}::{test_name}"], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-finite-lifecycle-contract-closure",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(path.relative_to(root)).replace("\\", "/")
            for path in (contract_tests, survival_tests, construction_tests, ecology_tests, economy_tests)
        ],
        "evidence": evidence,
        "run_id": f"infra-finite-lifecycle-contract-closure-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "contracts": "five existing StateDefinition rows plus the existing Economy wage-obligation row",
        "write_path": "existing owner -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "The reader has no registration or dispatch API and creates no writer.",
            "Ecology frost remains owner-local; it is not admitted to generic semantic settlement.",
            "No additional effect/state row, construction repair/transform, or generic lifecycle is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-finite-lifecycle-contract-closure-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1Q Finite Lifecycle Contract Closure Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_finite_lifecycle_contract_closure_report_json={path}")
    print(f"overall_infra_finite_lifecycle_contract_closure_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
