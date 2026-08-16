from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_reference_data_license_admission.py"
    cases = {
        "canonical_append_outbox": "test_inf4z_reference_dataset_register_appends_authority_outbox",
        "authoritative_branch_admission": "test_inf4z_authoritative_reference_dataset_admits_branch_without_production_write",
        "correction_projection_outbox": "test_inf4z_reference_dataset_correction_advances_view_revision_and_outbox",
        "revoked_preview_zero_write": "test_inf4z_reference_dataset_revocation_rejects_branch_without_production_write",
        "forged_digest_zero_write": "test_inf4z_forged_reference_dataset_digest_rejects_branch_without_write",
        "owner_zero_write": "test_inf4z_reference_data_owner_mismatch_is_zero_write",
        "revision_zero_write": "test_inf4z_reference_data_revision_conflict_is_zero_write",
        "duplicate_changed_duplicate": "test_inf4z_reference_data_duplicate_and_changed_duplicate_are_distinct",
        "privacy_scope_zero_write": "test_inf4z_reference_dataset_view_scope_and_preview_scope_are_zero_write",
        "full_checkpoint_tail_replay": "test_inf4z_reference_dataset_full_and_checkpoint_tail_replay_match",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-reference-data-license-admission-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-reference-data-license-admission",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-reference-data-license-admission-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "authority:reference_data",
        "stream": "gameplay:reference_data:{dataset_ref}",
        "event_types": ["gameplay.reference_data.dataset_registered", "gameplay.reference_data.dataset_corrected", "gameplay.reference_data.dataset_revoked"],
        "write_path": "ReferenceDataAuthority -> GameplayCommandEnvelope/SettlementPlan -> owner fragment -> GameplayEventStore.append_batch -> outbox/replay -> authority-scoped projection",
        "limitations": ["Only frozen authority-scoped dataset views admit calibration preview.", "No external ingestion, branch promotion, population truth, P6 or P7 is admitted."],
    }
    path = verification_dir(root) / "infra-reference-data-license-admission-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4Z Reference-Data License Admission Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_reference_data_license_admission_report_json={path}")
    print(f"overall_infra_reference_data_license_admission_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
