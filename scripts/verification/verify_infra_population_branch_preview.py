from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "versioned_reference_and_calibration": "test_reference_and_calibration_inputs_are_versioned_and_scoped",
        "deterministic_preview_and_production_isolation": "test_branch_preview_is_deterministic_and_does_not_append_production_events",
        "dataset_scope_zero_write": "test_branch_preview_rejects_dataset_scope_and_base_mismatch_without_writes",
        "shuffled_candidate_determinism": "test_inf4z_branch_preview_orders_shuffled_candidates_deterministically",
        "fixed_base_digest_zero_write": "test_inf4z_branch_preview_rejects_fixed_base_digest_without_production_writes",
        "calibration_digest_zero_write": "test_inf4z_branch_preview_rejects_fixed_base_digest_mismatch_without_production_writes",
        "unknown_profile_zero_write": "test_inf4z_branch_preview_rejects_unknown_candidate_profile_without_production_writes",
        "public_redaction_and_production_replay": "test_branch_report_redacts_public_data_and_production_replay_remains_equivalent",
        "isolated_branch_replay": "test_branch_buffer_replays_deterministically_without_production_append",
        "production_batch_idempotency_revision_and_checkpoint_tail": "test_production_batch_duplicate_revision_conflict_and_checkpoint_tail_are_explicit",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for name, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-population-branch-preview-{name}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[name] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-population-branch-preview",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-population-branch-preview-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/population_continuity/batch.py", "backend/app/population_continuity/branch_preview.py", "backend/app/character_agent/profile/registry.py"],
        "write_path": "production planner -> existing domain authority -> GameplayEventStore.append_batch; branch preview uses no production append path",
        "limitations": [
            "Family/organization inputs are scoped projection inputs only; full social authority, generated population truth, and civilization simulation remain out of scope.",
            "ReferenceDataset.license_ref is caller-provided metadata; authoritative unlicensed-calibration rejection remains blocked pending an approved existing owner, stream, scoped projection, and revision pin.",
        ],
    }
    path = verification_dir(root) / "infra-population-branch-preview-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4 Population Branch Preview Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_population_branch_preview_report_json={path}")
    print(f"overall_infra_population_branch_preview_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
