from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_civilization_capability_consumer.py"
    cases = {
        "government_owner_fragment_receipt": "test_inf4y_capability_gated_inspection_uses_existing_government_fragment_and_receipt",
        "event_capability_redaction": "test_inf4y_capability_gated_inspection_redacts_capability_details",
        "actor_scoped_outbox_projection": "test_inf4y_capability_gated_inspection_writes_actor_scoped_outbox_projection",
        "jurisdiction_mapping_zero_write": "test_inf4y_capability_gated_inspection_rejects_jurisdiction_mismatch_without_writes",
        "stale_capability_source_zero_write": "test_inf4y_capability_gated_inspection_stale_source_is_zero_write",
        "capability_effective_tick_zero_write": "test_inf4y_capability_gated_inspection_not_effective_is_zero_write",
        "capability_source_event_zero_write": "test_inf4y_capability_gated_inspection_source_event_forgery_is_zero_write",
        "revoked_capability_zero_write": "test_inf4y_capability_gated_inspection_revoked_source_is_zero_write",
        "forged_capability_input_zero_write": "test_inf4y_capability_gated_inspection_forged_input_is_zero_write",
        "capability_scope_zero_write": "test_inf4y_capability_gated_inspection_non_authority_scope_is_zero_write",
        "capability_policy_pin_zero_write": "test_inf4y_capability_gated_inspection_unpinned_policy_is_zero_write",
        "government_revision_zero_write": "test_inf4y_capability_gated_inspection_government_revision_conflict_is_zero_write",
        "merge_privacy_zero_write": "test_inf4y_capability_gated_inspection_merge_privacy_denial_is_zero_write",
        "idempotent_duplicate_and_changed_duplicate_zero_write": "test_inf4y_capability_gated_inspection_is_idempotent_and_changed_duplicate_is_zero_write",
        "full_checkpoint_tail_replay": "test_inf4y_capability_gated_inspection_replays_full_checkpoint_tail",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-civilization-capability-inspection-consumer-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-civilization-capability-inspection-consumer",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-civilization-capability-inspection-consumer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "read_owner": "authority:civilization_capability",
        "read_stream": "gameplay:civilization_capability:{jurisdiction_ref}",
        "target_owner": "actor_gameplay.government_domain",
        "target_stream": "gameplay:government:{organization_ref}",
        "event_type": "gameplay.government.inspection_recorded",
        "write_path": "authority-scoped capability view -> PopulationPlanner proposal -> GovernmentAuthority fragment -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only authority-scoped active capability views gate the named inspection row.",
            "The target jurisdiction is existing Government inspection data; capability source lineage never enters the event.",
            "Supply remains separately verified; work, semantic, and every unlisted consumer remain zero-write rejected.",
            "No civilization progression, six-axis propagation, institution system, population truth owner, P6, or P7 is created.",
        ],
    }
    path = verification_dir(root) / "infra-civilization-capability-inspection-consumer-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4Y Capability-Gated Inspection Consumer Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_civilization_capability_inspection_consumer_report_json={path}")
    print(f"overall_infra_civilization_capability_inspection_consumer_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
