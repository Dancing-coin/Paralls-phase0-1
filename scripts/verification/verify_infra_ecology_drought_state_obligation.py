from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    owner_tests = root / "backend" / "tests" / "test_infra_ecology_drought_state_obligation.py"
    semantic_tests = root / "backend" / "tests" / "test_infra_semantic_ecology_drought_adapter.py"
    owner_contract_tests = root / "backend" / "tests" / "test_infra_closed_state_owner_contract_matrix.py"
    lifecycle_contract_tests = root / "backend" / "tests" / "test_infra_finite_lifecycle_contract_closure.py"
    adapter_contract_tests = root / "backend" / "tests" / "test_infra_state_lifecycle_adapter_matrix.py"
    cases = {
        "owner_apply_on_existing_stream": f"{owner_tests}::test_ecology_drought_state_apply_commits_on_existing_ecology_stream",
        "owner_missing_source_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_missing_source_without_write",
        "owner_exact_duplicate_replay": f"{owner_tests}::test_ecology_drought_state_duplicate_replays_without_second_append",
        "owner_changed_duplicate_zero_write": f"{owner_tests}::test_ecology_drought_state_changed_duplicate_is_zero_write",
        "owner_revision_conflict_zero_write": f"{owner_tests}::test_ecology_drought_state_revision_conflict_is_zero_write",
        "owner_command_privacy_zero_write": f"{owner_tests}::test_ecology_drought_state_nonproject_privacy_is_zero_write",
        "owner_catalog_guard_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_catalog_owner_guard_without_write",
        "owner_wrong_effect_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_wrong_effect_without_write",
        "owner_wrong_definition_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_wrong_definition_without_write",
        "owner_due_expiry_through_ecology": f"{owner_tests}::test_ecology_drought_state_due_expiry_settles_through_existing_coordinator",
        "owner_opening_provenance_zero_write": f"{owner_tests}::test_ecology_drought_state_fragment_rejects_missing_opening_event_provenance_without_write",
        "owner_outbox_and_receipt": f"{owner_tests}::test_ecology_drought_state_outbox_and_receipt_are_append_derived",
        "owner_full_replay": f"{owner_tests}::test_ecology_drought_state_full_replay_rebuilds_committed_history",
        "owner_checkpoint_tail_replay": f"{owner_tests}::test_ecology_drought_state_checkpoint_tail_replay_matches_full_replay",
        "owner_private_source_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_private_source_without_write",
        "owner_forged_source_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_forged_source_without_write",
        "owner_stale_source_revision_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_stale_source_revision_without_write",
        "owner_historical_source_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_historical_source_after_newer_process_without_write",
        "owner_historical_exact_duplicate_replay": f"{owner_tests}::test_ecology_drought_state_replays_exact_duplicate_after_newer_process_without_write",
        "owner_second_active_obligation_zero_write": f"{owner_tests}::test_ecology_drought_state_rejects_second_active_obligation_without_write",
        "semantic_closed_input_shape": f"{semantic_tests}::test_semantic_ecology_drought_command_forbids_free_owner_stream_and_payload_fields",
        "semantic_owner_append": f"{semantic_tests}::test_semantic_ecology_drought_maps_only_to_existing_ecology_owner_append",
        "semantic_revision_zero_write": f"{semantic_tests}::test_semantic_ecology_drought_rejects_stale_revision_without_write",
        "semantic_snapshot_zero_write": f"{semantic_tests}::test_semantic_ecology_drought_rejects_snapshot_mismatch_without_write",
        "semantic_exact_duplicate_replay": f"{semantic_tests}::test_semantic_ecology_drought_replays_exact_duplicate_without_second_write",
        "semantic_changed_duplicate_zero_write": f"{semantic_tests}::test_semantic_ecology_drought_rejects_changed_duplicate_without_write",
        "semantic_private_source_zero_write": f"{semantic_tests}::test_semantic_ecology_drought_rejects_private_source_without_write",
        "semantic_adapter_guard_zero_write": f"{semantic_tests}::test_semantic_ecology_drought_requires_closed_adapter_matrix_row_without_write",
        "semantic_checkpoint_tail_replay": f"{semantic_tests}::test_semantic_ecology_drought_reuses_ecology_checkpoint_tail_replay",
        "finite_state_owner_row": f"{owner_contract_tests}::test_closed_state_owner_contract_matrix_fixes_ecology_drought_event_family_and_privacy",
        "finite_lifecycle_row": f"{lifecycle_contract_tests}::test_finite_lifecycle_contract_reader_exposes_drought_projection_revision_idempotency_and_replay_metadata",
        "finite_adapter_row": f"{adapter_contract_tests}::test_closed_adapter_matrix_admits_ecology_drought_apply_only",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, nodeid in cases.items():
        log_path = verification_dir(root) / f"infra-ecology-drought-state-obligation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", nodeid], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-ecology-drought-state-obligation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [
            str(owner_tests.relative_to(root)).replace("\\", "/"),
            str(semantic_tests.relative_to(root)).replace("\\", "/"),
            str(owner_contract_tests.relative_to(root)).replace("\\", "/"),
            str(lifecycle_contract_tests.relative_to(root)).replace("\\", "/"),
            str(adapter_contract_tests.relative_to(root)).replace("\\", "/"),
        ],
        "evidence": evidence,
        "run_id": f"infra-ecology-drought-state-obligation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": "EcologyHazardAuthority",
        "stream": "gameplay:ecology:{region_ref}",
        "policy": "policy:ecology_drought_state_expiry@1",
        "canonical_source": "committed project-visible gameplay.ecology.drought_process_advanced",
        "semantic_entry": "SemanticSettlementAuthority.settle_closed_ecology_drought",
        "write_path": "Semantic proposal -> EcologyHazardAuthority -> GameplayCommandEnvelope/OwnerAuthorizedFragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only the seventh finite row effect:drought -> state:drought@1 is admitted.",
            "This profile does not authorize a generic lifecycle router, scheduler, consumer edge, or direct semantic append path.",
        ],
    }
    path = verification_dir(root) / "infra-ecology-drought-state-obligation-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-1AA Ecology Drought State Obligation Report",
        {
            "results": [
                {"id": key, "status": "proved" if value else "missing", "title": key}
                for key, value in checks.items()
            ],
            "overall_passed": report["overall_passed"],
        },
        "overall_passed",
    )
    print(f"infra_ecology_drought_state_obligation_report_json={path}")
    print(f"overall_infra_ecology_drought_state_obligation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
