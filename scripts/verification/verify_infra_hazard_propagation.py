from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_hazard_propagation.py"
    cases = {
        "registered_edge_success": "test_registered_canonical_frost_edge_commits_one_construction_owner_fragment",
        "unknown_edge_zero_write": "test_unknown_canonical_hazard_edge_is_zero_write",
        "disabled_edge_zero_write": "test_disabled_canonical_hazard_edge_is_zero_write",
        "missing_source_zero_write": "test_missing_canonical_hazard_source_is_zero_write",
        "stale_source_revision_zero_write": "test_stale_canonical_hazard_source_revision_is_zero_write",
        "privacy_scope_zero_write": "test_canonical_hazard_privacy_scope_is_zero_write",
        "direct_consumer_zero_write": "test_canonical_hazard_direct_consumer_invocation_is_zero_write",
        "forged_authority_zero_write": "test_forged_ecology_command_without_transient_admission_is_zero_write",
        "forged_real_class_admission_zero_write": "test_real_class_forged_canonical_hazard_admission_is_zero_write",
        "module_api_issuance_fence": "test_module_api_cannot_issue_forged_canonical_hazard_admission",
        "source_visibility_zero_write": "test_authority_only_canonical_source_cannot_propose_a_project_edge",
        "retired_source_zero_write": "test_retired_canonical_hazard_cannot_propose_an_edge_or_write",
        "exact_crop_pin": "test_canonical_hazard_pins_exact_linked_crop_with_multiple_crops_in_region",
        "missing_linked_crop_zero_write": "test_canonical_hazard_without_an_active_linked_crop_is_zero_write",
        "idempotency_and_source_conflict": "test_canonical_hazard_edge_is_idempotent_and_source_revision_conflicts_after_proposal",
        "scoped_projection_checkpoint_tail_replay": "test_canonical_hazard_edge_scopes_provenance_and_replays_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    logs: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-hazard-propagation-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        logs.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-hazard-propagation",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": logs,
        "run_id": f"infra-hazard-propagation-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "enabled_edges": [{
            "edge_ref": "ecology-hazard:frost-to-construction-finish:v1",
            "source_owner": "authority:ecology",
            "source_stream": "gameplay:ecology:{region_ref}",
            "source_events": ["gameplay.ecology.hazard.recorded", "gameplay.ecology.crop.recorded"],
            "consumer_owner": "ConstructionProductionAuthority",
            "target_stream": "gameplay:construction_production:{facility_ref}",
            "target_event": "gameplay.construction_production.run_finished",
        }],
        "write_path": "EcologyHazardAuthority proposal -> ConstructionProductionAuthority OwnerAuthorizedFragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only project-visible canonical frost records may enter this one edge.",
            "No delayed row, retry, compensation, generic fanout, market/body/social/population consumer, or P6/P7 capability is enabled.",
        ],
    }
    path = verification_dir(root) / "infra-hazard-propagation-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-3Y Hazard Propagation Report", {"results": [{"id": name, "status": "proved" if ok else "missing", "title": name} for name, ok in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_hazard_propagation_report_json={path}")
    print(f"overall_infra_hazard_propagation_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
