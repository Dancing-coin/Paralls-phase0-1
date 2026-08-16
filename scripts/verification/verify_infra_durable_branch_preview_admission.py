from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    passed_path = root / "backend" / "tests" / "test_infra_government_branch_scenario.py"
    failed_path = root / "backend" / "tests" / "test_infra_government_failed_inspection_remediation_scenario.py"
    cases = {
        "passed_admission_evidence": (passed_path, "test_government_branch_scenario_derives_passed_row_from_durable_preview_admission"),
        "failed_admission_evidence": (failed_path, "test_failed_inspection_remediation_derives_row_from_durable_preview_admission"),
        "missing_admission_zero_write": (passed_path, "test_government_branch_scenario_rejects_missing_durable_preview_admission_without_append"),
        "passed_cross_branch_stream_zero_write": (passed_path, "test_government_branch_scenario_rejects_cross_branch_preview_stream_without_append"),
        "failed_cross_branch_stream_zero_write": (failed_path, "test_failed_inspection_remediation_rejects_cross_branch_preview_stream_without_append"),
        "primitive_provenance_zero_write": (failed_path, "test_direct_forged_government_remediation_submission_is_zero_write"),
        "passed_duplicate_idempotency": (passed_path, "test_government_branch_scenario_duplicate_idempotency_replays_without_second_append"),
        "failed_duplicate_idempotency": (failed_path, "test_failed_inspection_remediation_duplicate_replays_without_second_append"),
        "source_revision_zero_write": (failed_path, "test_failed_inspection_remediation_rejects_stale_government_source_without_append"),
        "creator_debug_outbox": (failed_path, "test_failed_inspection_remediation_outbox_is_creator_debug_scoped"),
        "scenario_checkpoint_tail_replay": (failed_path, "test_failed_inspection_remediation_projection_replays_checkpoint_tail"),
        "production_and_promotion_zero_write": (failed_path, "test_failed_inspection_remediation_keeps_production_replay_and_promotion_zero_write"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-durable-branch-preview-admission-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-durable-branch-preview-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(passed_path.relative_to(root)).replace("\\", "/"), str(failed_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-durable-branch-preview-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "BranchPreviewAuthority evidence -> GovernmentAuthority scenario",
        "stream": "gameplay:branch_preview:{branch_ref} -> gameplay:government_branch:{branch_ref}:{organization_ref}",
        "event": "gameplay.branch_preview.inspection_admission_recorded",
        "limitations": [
            "The evidence stream records accepted proposal evidence only; it is not population, social or production truth.",
            "No generic receipt, remediation lifecycle, promotion, scheduler or second store is introduced.",
        ],
    }
    path = verification_dir(root) / "infra-durable-branch-preview-admission-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4L Durable Branch Preview Admission Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_durable_branch_preview_admission_report_json={path}")
    print(f"overall_infra_durable_branch_preview_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
