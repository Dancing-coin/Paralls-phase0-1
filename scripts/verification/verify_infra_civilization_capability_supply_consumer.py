from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_infra_civilization_capability_consumer.py"
    cases = {
        "organization_owner_fragment_receipt": "test_inf4y_capability_gated_supply_uses_existing_organization_fragment_and_receipt",
        "event_capability_redaction": "test_inf4y_capability_gated_supply_event_redacts_capability_details",
        "stale_capability_source_zero_write": "test_inf4y_capability_stale_revision_is_zero_write_before_organization_owner",
        "capability_digest_zero_write": "test_inf4y_capability_digest_forgery_is_zero_write",
        "capability_effective_tick_zero_write": "test_inf4y_capability_not_effective_is_zero_write",
        "capability_scope_zero_write": "test_inf4y_capability_non_authority_scope_is_zero_write",
        "capability_source_event_zero_write": "test_inf4y_capability_source_event_forgery_is_zero_write",
        "candidate_mapping_zero_write": "test_inf4y_capability_candidate_mapping_mismatch_is_zero_write",
        "unapproved_intent_zero_write": "test_inf4y_capability_gated_supply_rejects_unapproved_intent_without_writes",
        "capability_policy_pin_zero_write": "test_inf4y_capability_policy_must_be_pinned_in_active_revisions_without_writes",
        "revoked_capability_zero_write": "test_inf4y_revoked_capability_is_zero_write_before_organization_owner",
        "organization_revision_zero_write": "test_inf4y_organization_revision_conflict_is_zero_write_after_capability_admission",
        "idempotent_duplicate": "test_inf4y_capability_gated_supply_is_idempotent",
        "full_checkpoint_tail_replay": "test_inf4y_capability_gated_supply_replays_full_checkpoint_tail",
        "source_stream_revision_independent": "test_inf4y_capability_stream_revision_is_pinned_independently_from_capability_revision",
        "changed_duplicate_zero_write": "test_inf4y_changed_capability_gated_duplicate_is_zero_write",
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, test_name in cases.items():
        log_path = verification_dir(root) / f"infra-civilization-capability-supply-consumer-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-civilization-capability-supply-consumer",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-civilization-capability-supply-consumer-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "read_owner": "authority:civilization_capability",
        "read_stream": "gameplay:civilization_capability:{jurisdiction_ref}",
        "target_owner": "actor_gameplay.organization_domain",
        "target_stream": "gameplay:organization:{organization_ref}",
        "event_type": "gameplay.organization.commerce_commitment_accepted",
        "write_path": "authority-scoped capability view -> PopulationPlanner proposal -> OrganizationAuthority fragment -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only authority-scoped active capability views gate the named supply row.",
            "Inspection, work, semantic, and every unlisted consumer path remain zero-write rejected.",
            "No civilization progression, six-axis propagation, institution system, population truth owner, P6, or P7 is created.",
        ],
    }
    path = verification_dir(root) / "infra-civilization-capability-supply-consumer-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-4Y Capability-Gated Supply Consumer Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_civilization_capability_supply_consumer_report_json={path}")
    print(f"overall_infra_civilization_capability_supply_consumer_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
