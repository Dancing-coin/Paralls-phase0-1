from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    matrix = root / "backend" / "tests" / "test_infra_closed_state_owner_contract_matrix.py"
    survival = root / "backend" / "tests" / "test_infra_survival_state_obligation.py"
    construction = root / "backend" / "tests" / "test_infra_construction_maintenance_state_owner.py"
    ecology = root / "backend" / "tests" / "test_infra_ecology_frost_state_obligation.py"
    cases = {
        "five_row_matrix_shape": (matrix, "test_closed_state_owner_contract_matrix_materializes_all_admitted_rows"),
        "unknown_row_zero_write": (matrix, "test_closed_state_owner_contract_matrix_rejects_unregistered_pairs"),
        "fixed_ecology_contract": (matrix, "test_closed_state_owner_contract_matrix_fixes_ecology_event_family_and_privacy"),
        "survival_contract_enforced_zero_write": (survival, "test_survival_state_rejects_forged_shared_owner_contract_without_write"),
        "construction_contract_enforced_zero_write": (construction, "test_construction_maintenance_rejects_forged_shared_owner_contract_without_append"),
        "ecology_contract_enforced_zero_write": (ecology, "test_ecology_frost_crop_state_rejects_forged_shared_owner_contract_without_write"),
        "survival_lifecycle_replay": (survival, "test_survival_state_transform_cancels_prior_expiry_and_rebuilds_from_checkpoint_tail"),
        "construction_privacy_projection": (construction, "test_construction_maintenance_owner_row_emits_project_scoped_outbox_and_projection"),
        "ecology_replay": (ecology, "test_ecology_frost_crop_state_checkpoint_tail_replay_matches_full_replay"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-closed-state-owner-contract-matrix-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-closed-state-owner-contract-matrix",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(path.relative_to(root)).replace("\\", "/") for path in (matrix, survival, construction, ecology)],
        "evidence": evidence,
        "run_id": f"infra-closed-state-owner-contract-matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["SurvivalAuthority", "ConstructionProductionAuthority", "EcologyHazardAuthority"],
        "write_path": "existing owner -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "The matrix contains exactly five admitted StateDefinition rows.",
            "It is not open registration, generic dispatch, or a generic writer.",
        ],
    }
    path = verification_dir(root) / "infra-closed-state-owner-contract-matrix-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1M Closed State Owner Contract Matrix Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_closed_state_owner_contract_matrix_report_json={path}")
    print(f"overall_infra_closed_state_owner_contract_matrix_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
