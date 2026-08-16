from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    cases = {
        "closed_terminal_operation_shape": "test_reusable_lifecycle_contract_exposes_closed_terminal_operation_shape",
        "canonical_registry_factory": "test_default_coordinator_uses_the_same_closed_registration_source",
        "explicit_empty_zero_write_fence": "test_explicit_empty_registration_set_remains_a_zero_write_fence",
        "full_checkpoint_tail_replay": "test_closed_projection_replay_is_identical_for_full_and_checkpoint_tail",
    }
    test_path = root / "backend" / "tests" / "test_infra_reusable_lifecycle_contract.py"
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-reusable-lifecycle-contract-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    existing = {
        "survival_two_owner_projection": "backend/tests/test_infra_generic_obligation_lifecycle.py::test_lifecycle_projection_rebuilds_open_obligations_for_two_registered_owners",
        "survival_due_read_only": "backend/tests/test_infra_generic_obligation_lifecycle.py::test_lifecycle_projection_derives_due_without_writing_a_second_lifecycle_fact",
        "economy_terminal_replay": "backend/tests/test_infra_economy_wage_terminal_lifecycle.py::test_economy_wage_expiry_is_project_scoped_and_checkpoint_tail_replayable",
    }
    for check, node in existing.items():
        log_path = verification_dir(root) / f"infra-reusable-lifecycle-contract-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", node], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))

    report = {
        "profile": "infra-reusable-lifecycle-contract",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-reusable-lifecycle-contract-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["actor_gameplay.survival_domain", "actor_gameplay.econ1_economy_domain"],
        "write_path": "existing owner -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "This normalizes the reusable lifecycle contract only; it does not add caller policy registration or generic business settlement.",
            "Construction and ecology remain their existing finite owner rows; no new owner or event family is admitted.",
        ],
    }
    path = verification_dir(root) / "infra-reusable-lifecycle-contract-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-2C2 Reusable Lifecycle Contract Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_reusable_lifecycle_contract_report_json={path}")
    print(f"overall_infra_reusable_lifecycle_contract_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
