from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    binding = root / "backend" / "tests" / "test_infra_activation_obligation_binding_contract.py"
    cold = root / "backend" / "tests" / "test_infra_activation_survival_expiry.py"
    dehydration = root / "backend" / "tests" / "test_infra_activation_dehydration_expiry.py"
    overheated = root / "backend" / "tests" / "test_infra_activation_overheated_expiry.py"
    activation = root / "backend" / "tests" / "test_population_continuity.py"
    schedule = root / "backend" / "tests" / "test_infra_household_org_source_projection.py"
    cases = {
        "exact_four_row_contract": (binding, "test_activation_obligation_binding_contract_has_exact_four_existing_owner_rows"),
        "unknown_kind_lookup_rejected": (binding, "test_unknown_pending_kind_has_no_activation_obligation_binding"),
        "event_derived_binding_reference": (binding, "test_pending_event_persists_contract_derived_binding_ref"),
        "forged_binding_zero_activation_write": (binding, "test_forged_pending_binding_ref_is_zero_write"),
        "unbound_historical_pending_zero_target_write": (binding, "test_released_unbound_historical_pending_cannot_replay_existing_survival_settlement"),
        "pending_duplicate_idempotency": (activation, "test_activation_schedule_pending_duplicate_is_idempotent"),
        "pending_privacy_scope": (activation, "test_activation_schedule_pending_privacy_scope_filters_view"),
        "pending_checkpoint_tail_replay": (activation, "test_activation_schedule_pending_checkpoint_tail_replay_matches_full"),
        "cold_survival_owner_settlement": (cold, "test_released_survival_expiry_pending_settles_only_through_existing_survival_fragment"),
        "dehydrated_duplicate_target_zero_write": (dehydration, "test_released_dehydration_pending_replays_duplicate_without_second_target_write"),
        "overheated_privacy_zero_target_write": (overheated, "test_released_overheated_pending_rejects_nonproject_privacy_without_target_write"),
        "survival_receipt_separation": (overheated, "test_overheated_release_and_survival_settlement_have_distinct_append_receipts"),
        "schedule_owner_fragment_settlement": (schedule, "test_released_activation_pending_schedule_merges_only_through_existing_organization_owner"),
        "schedule_forgery_zero_target_write": (schedule, "test_activation_pending_schedule_forgery_or_stale_release_is_zero_write_at_organization_boundary"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-activation-obligation-binding-contract-{check}.log"
        result = run_command(
            [python, "-m", "pytest", "-q", str(test_path), "-k", test_name],
            root,
            log_path,
        )
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-activation-obligation-binding-contract",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(path.relative_to(root)).replace("\\", "/") for path in (binding, cold, dehydration, overheated, activation, schedule)],
        "evidence": evidence,
        "run_id": f"infra-activation-obligation-binding-contract-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["ProfileActivationAuthority", "SurvivalAuthority", "OrganizationAuthority"],
        "activation_stream": "population:{world_ref}",
        "write_path": "activation pending/release append -> event-derived closed binding projection -> existing Survival or Organization owner fragment -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "receipt_boundary": "activation receipt and target-owner receipt remain separate append-derived results",
        "limitations": [
            "The contract has exactly three Survival state-expiry rows and one schedule-gated Organization supply row.",
            "It is not registration, a generic pending queue, a generic fragment dispatcher, payment/account truth, or a cross-stream atomic receipt.",
            "Historical structurally valid unregistered Survival pending diagnostics remain unbound and are zero-write at the target owner boundary.",
        ],
    }
    path = verification_dir(root) / "infra-activation-obligation-binding-contract-report.json"
    write_json(path, report)
    write_markdown(
        path.with_suffix(".md"),
        "INF-2G Activation-Obligation Binding Contract Report",
        {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]},
        "overall_passed",
    )
    print(f"infra_activation_obligation_binding_contract_report_json={path}")
    print(f"overall_infra_activation_obligation_binding_contract_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
