from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root(); python = resolve_python_exe(None); tests = root / "backend" / "tests"
    cases = {
        "matrix_shape_and_survival_apply": ("test_infra_state_lifecycle_adapter_matrix.py", "test_closed_adapter_matrix_exposes_only_existing_semantic_owner_adapters"),
        "unsupported_operation_zero_write": ("test_infra_state_lifecycle_adapter_matrix.py", "test_closed_adapter_matrix_rejects_unadmitted_owner_operation"),
        "survival_action_owner_commit": ("test_infra_semantic_survival_state_action.py", "test_semantic_survival_state_dispel_commits_existing_owner_events"),
        "survival_privacy": ("test_infra_semantic_survival_state_action.py", "test_semantic_survival_state_action_outbox_is_project_scoped"),
        "survival_checkpoint_replay": ("test_infra_semantic_survival_state_action.py", "test_semantic_survival_state_action_replays_full_and_checkpoint_tail"),
        "construction_action_owner_commit": ("test_infra_construction_maintenance_state_action.py", "test_semantic_construction_maintenance_dispel_clears_state_and_cancels_open_obligation_in_one_batch"),
        "construction_duplicate": ("test_infra_construction_maintenance_state_action.py", "test_semantic_construction_maintenance_dispel_replays_exact_duplicate_without_write"),
        "construction_revision": ("test_infra_construction_maintenance_state_action.py", "test_semantic_construction_maintenance_dispel_rejects_revision_conflict_without_write"),
        "construction_privacy": ("test_infra_construction_maintenance_state_action.py", "test_semantic_construction_maintenance_dispel_rejects_nonproject_privacy_without_write"),
        "construction_checkpoint_replay": ("test_infra_construction_maintenance_state_action.py", "test_semantic_construction_maintenance_dispel_checkpoint_tail_replay_matches_full_projection"),
    }
    checks: dict[str, bool] = {}; logs: list[str] = []
    for check, (filename, test_name) in cases.items():
        log = verification_dir(root) / f"infra-state-lifecycle-adapter-matrix-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(tests / filename), "-k", test_name], root, log)
        checks[check] = result.returncode == 0; logs.append(str(log.relative_to(root)).replace("\\", "/"))
    report = {"profile": "infra-state-lifecycle-adapter-matrix", "overall_passed": all(checks.values()), "checks": checks, "evidence": logs, "run_id": f"infra-state-lifecycle-adapter-matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "write_path": "semantic admission -> existing Survival/Construction authority -> one GameplayEventStore.append_batch -> scoped projection/replay", "limitations": ["Ecology and Economy have no semantic proposal adapter and remain unsupported.", "The matrix admits only fixed existing owner rows; it is not caller-open registration or a generic writer."]}
    path = verification_dir(root) / "infra-state-lifecycle-adapter-matrix-report.json"; write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-1W State Lifecycle Adapter Matrix Report", {"results": [{"id": key, "status": "proved" if passed else "missing", "title": key} for key, passed in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_state_lifecycle_adapter_matrix_report_json={path}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
