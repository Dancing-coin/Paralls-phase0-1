from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_regional_ecology_truth.py"
    cases = {
        "region_recorded": "test_ecology_region_recorded_event_is_canonical",
        "environment_recorded": "test_ecology_environment_recorded_event_is_canonical",
        "resource_recorded": "test_ecology_resource_recorded_event_is_canonical",
        "crop_recorded": "test_ecology_crop_recorded_event_is_canonical",
        "hazard_recorded": "test_ecology_hazard_recorded_event_is_canonical",
        "region_retired": "test_ecology_region_retired_event_is_canonical",
        "environment_retired": "test_ecology_environment_retired_event_is_canonical",
        "resource_retired": "test_ecology_resource_retired_event_is_canonical",
        "crop_retired": "test_ecology_crop_retired_event_is_canonical",
        "hazard_retired": "test_ecology_hazard_retired_event_is_canonical",
        "existing_stream_one_append_outbox": "test_ecology_authority_records_all_canonical_region_facts_through_one_existing_stream",
        "region_revision_zero_write": "test_ecology_region_bundle_rejects_revision_or_region_mismatch_without_writes",
        "record_revision_zero_write": "test_ecology_single_record_rejects_uncommitted_or_skipped_record_revision",
        "retirement_unknown_zero_write": "test_ecology_retirement_of_unknown_or_wrong_revision_is_zero_write",
        "privacy_bundle_overwrite_zero_write": "test_ecology_private_or_bundle_overwrite_is_zero_write",
        "retirement_idempotency": "test_ecology_retirement_is_owner_fragment_event_derived_and_idempotent",
        "scoped_privacy": "test_ecology_authority_only_visibility_is_hidden_from_public_projection",
        "public_authority_replay": "test_ecology_region_projection_is_scope_filtered_and_checkpoint_tail_equivalent",
        "record_update": "test_ecology_update_replaces_one_record_only_after_owner_revision_check",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-regional-ecology-truth-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-regional-ecology-truth",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-regional-ecology-truth-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": ["backend/app/gameplay/ecology_runtime.py"],
        "stream": "gameplay:ecology:{region_ref}",
        "write_path": "EcologyHazardAuthority -> OwnerAuthorizedFragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "event_rows": ["region", "environment", "resource", "crop", "hazard"],
        "limitations": [
            "No ecology scheduler, regeneration/growth obligation, retry, compensation, or consumer propagation is admitted.",
            "Frost semantic settlement remains its existing crop-owner path and does not become a regional record write.",
        ],
    }
    path = verification_dir(root) / "infra-regional-ecology-truth-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3X Regional Ecology Truth Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_regional_ecology_truth_report_json={path}")
    print(f"overall_infra_regional_ecology_truth_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
