from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = [
        "backend/tests/test_world_admin_auth_service.py",
        "backend/tests/test_world_admin_cadence_revocation_application.py",
        "backend/tests/test_world_replay_checkpoint_application.py::test_inventory_participant_survives_durable_reopen_and_checkpoint_tail",
        "backend/tests/test_siming_population_inventory_vertical.py::test_inventory_caller_freezes_complete_settlement_window_from_read_set",
        "backend/tests/test_siming_population_inventory_vertical.py::test_inventory_read_source_freezes_activation_binding_without_writing",
        "backend/tests/test_siming_population_inventory_vertical.py::test_inventory_owner_rejects_changed_frozen_content_pin_before_write",
        "backend/tests/test_population_conflict_cadence.py",
        "backend/tests/test_economy_temporal_replay_application.py::test_economy_and_ecology_share_application_checkpoint_tail_after_durable_restart",
        "backend/tests/test_economy_temporal_replay_application.py::test_economy_application_strict_grant_rejection_is_zero_write",
        "backend/tests/test_ecology_temporal_consumer.py::test_each_consumer_budget_excludes_other_domain_due_obligations",
        "backend/tests/test_ecology_temporal_consumer.py::test_ecology_temporal_consumer_uses_confirmed_population_tick_and_existing_owner",
        "backend/tests/test_infra_construction_maintenance_state_owner.py::test_construction_maintenance_owner_row_appends_fixed_state_event",
        "backend/tests/test_infra_construction_maintenance_state_owner.py::test_construction_maintenance_owner_row_full_and_checkpoint_tail_projection_match",
        "backend/tests/test_infra_construction_maintenance_state_action.py::test_semantic_construction_maintenance_dispel_clears_state_and_cancels_open_obligation_in_one_batch",
        "backend/tests/test_infra_semantic_ecology_frost_adapter.py::test_semantic_ecology_frost_maps_only_to_existing_ecology_owner_append",
        "backend/tests/test_infra_semantic_ecology_frost_adapter.py::test_semantic_ecology_frost_reuses_ecology_checkpoint_tail_replay",
        "backend/tests/test_infra_payroll_operating_window_closure.py::test_payroll_window_closure_success_uses_organization_window_owner_and_economy_payment",
        "backend/tests/test_infra_payroll_operating_window_closure.py::test_payroll_window_closure_invalid_or_unverified_evidence_is_zero_write",
        "backend/tests/test_infra_payroll_operating_window_closure.py::test_payroll_window_closure_duplicate_idempotency_replays_without_second_write",
        "backend/tests/test_infra_payroll_operating_window_closure.py::test_payroll_window_closure_stale_revision_is_zero_write",
        "backend/tests/test_infra_payroll_operating_window_closure.py::test_payroll_window_closure_full_and_checkpoint_tail_replay_match",
        "backend/tests/test_infra_civilization_capability_consumer.py::test_inf4y_capability_gated_inspection_uses_existing_government_fragment_and_receipt",
        "backend/tests/test_infra_civilization_capability_consumer.py::test_inf4y_capability_gated_inspection_replays_full_checkpoint_tail",
        "backend/tests/test_infra_civilization_capability_consumer.py::test_inf4y_capability_gated_supply_uses_existing_organization_fragment_and_receipt",
        "backend/tests/test_infra_civilization_capability_consumer.py::test_inf4y_capability_gated_supply_replays_full_checkpoint_tail",
        "backend/tests/test_infra_semantic_survival_state_action.py::test_semantic_survival_state_dispel_commits_existing_owner_events",
        "backend/tests/test_infra_semantic_survival_state_action.py::test_semantic_survival_state_transform_commits_fixed_recovery_owner_events",
        "backend/tests/test_infra_semantic_survival_state_action.py::test_semantic_survival_state_action_replays_full_and_checkpoint_tail",
        "backend/tests/test_status_application_lifecycle.py::test_application_caller_durable_shutdown_restart_receipts_and_duplicate_dispatch",
        "backend/tests/test_status_application_lifecycle.py::test_missing_confirmed_temporal_pins_zero_write_in_strict_mode",
        "backend/tests/test_status_application_lifecycle.py::test_missing_mapping_on_restart_preserves_committed_status_and_denies_startup",
        "backend/tests/test_infra_economy_scheduled_transfer_obligation.py",
        "backend/tests/test_infra_economy_tax_obligation.py",
        "backend/tests/test_infra_economy_wage_obligation.py",
        "backend/tests/test_infra_construction_maintenance_state_obligation.py",
        "backend/tests/test_infra_ecology_drought_state_obligation.py",
        "backend/tests/test_infra_semantic_ecology_drought_adapter.py",
        "backend/tests/test_infra_ecology_frost_state_obligation.py",
        "backend/tests/test_infra_survival_dehydration_state_obligation.py",
        "backend/tests/test_infra_survival_heat_state_obligation.py",
        "backend/tests/test_infra_activation_survival_expiry.py::test_released_fatigue_expiry_pending_settles_through_existing_survival_fragment",
        "backend/tests/test_infra_activation_overheated_expiry.py",
        "backend/tests/test_infra_survival_state_obligation.py",
        "backend/tests/test_infra_activation_dehydration_expiry.py",
        "backend/tests/test_infra_activation_survival_expiry.py",
        "backend/tests/test_population_continuity.py::test_activation_lock_records_replayable_schedule_pending_then_releases",
        "backend/tests/test_population_continuity.py::test_activation_schedule_pending_rejects_free_form_payload_without_writes",
        "backend/tests/test_population_continuity.py::test_activation_schedule_pending_duplicate_is_idempotent",
        "backend/tests/test_population_continuity.py::test_activation_schedule_pending_privacy_scope_filters_view",
        "backend/tests/test_population_continuity.py::test_activation_schedule_pending_checkpoint_tail_replay_matches_full",
        "backend/tests/test_infra_activation_profile_region_assignment.py",
        "backend/tests/test_infra_economy_account_settlement_spine.py",
        "backend/tests/test_infra_organization_economy_commerce_commitment.py",
        "backend/tests/test_infra_economy_wage_terminal_lifecycle.py",
        "backend/tests/test_infra_ecology_weather_front_economy_quote_edge.py",
        "backend/tests/test_infra_ecology_weather_front_economy_quote_fanout.py",
        "backend/tests/test_infra_household_org_source_projection.py::test_released_activation_pending_schedule_merges_only_through_existing_organization_owner",
        "backend/tests/test_infra_household_org_source_projection.py::test_activation_pending_schedule_forgery_or_stale_release_is_zero_write_at_organization_boundary",
        "backend/tests/test_social_delivery_caller.py::test_government_notice_with_authored_validity_commits_through_production_caller",
        "backend/tests/test_social_delivery_caller.py::test_government_notice_production_caller_recovers_after_lost_append_response",
        "backend/tests/test_social_delivery_caller.py::test_government_notice_expiry_uses_bound_source_and_replays_changed_duplicates",
        "backend/tests/test_social_delivery_caller.py::test_government_notice_expiry_rejects_before_world_window_closes_without_write",
        "backend/tests/test_social_delivery_caller.py::test_government_notice_expiry_recovers_lost_response",
        "backend/tests/test_social_delivery_caller.py::test_application_social_ingress_commits_bound_delivery_from_durable_source",
        "backend/tests/test_social_delivery_caller.py::test_government_production_caller_checkpoint_tail_survives_durable_new_authority",
        "backend/tests/test_siming_population_contracts.py",
        "backend/tests/test_action_temporal_application.py::test_caller_activation_refuses_provider_switch_without_migration",
        "backend/tests/test_action_temporal_application.py::test_actual_caller_same_provider_mutation_requires_migration_and_old_replay_works",
        "backend/tests/test_life_state_case_death_caller.py",
        "backend/tests/test_population_activation_presence_service.py",
        "backend/tests/test_population_presence_runtime.py",
        "backend/tests/test_population_presence_replay_participant.py",
        "backend/tests/test_population_economy_random_application.py",
        "backend/tests/test_equipment_command_application.py",
        "backend/tests/test_equipment_command_service.py",
        "backend/tests/test_equipment_prediction_service.py",
    ]
    log = Path(tempfile.gettempdir()) / "paralls-admitted-participant-matrix.log"
    result = run_command([python, "-m", "pytest", "-q", *tests], root, log, timeout_seconds=3000)
    passed = result.returncode == 0 and bool(result.stdout.strip())
    log.unlink(missing_ok=True)
    command_log = verification_dir(root) / "command.log"
    evidence = [artifact_ref(root, command_log).replace("\\", "/")] if command_log.is_file() else []
    participants = [
            "inventory_custody",
            "character_temporal_admission",
            "economy_temporal",
            "ecology_temporal",
            "construction_maintenance_state_owner",
            "construction_maintenance_state_action",
            "ecology_semantic_frost_adapter",
            "organization_operating_window_econ1_wage_batch",
            "civilization_capability_government_inspection",
            "civilization_capability_organization_supply",
            "survival_semantic_state_action",
            "status_temporal_application",
            "economy_scheduled_transfer_obligation",
            "economy_tax_obligation",
            "economy_wage_obligation",
            "construction_maintenance_state_obligation",
            "ecology_drought_state_obligation",
            "ecology_semantic_drought_adapter",
            "ecology_frost_state_obligation",
            "survival_dehydration_state_obligation",
            "survival_heat_state_obligation",
            "activation_fatigue_to_survival_expiry",
            "activation_overheated_to_survival_expiry",
            "survival_cold_state_obligation",
            "activation_dehydrated_to_survival_expiry",
            "activation_cold_to_survival_expiry",
            "activation_pending_schedule_to_organization",
            "activation_profile_region_assignment",
            "economy_account_settlement_spine",
            "organization_economy_commerce_commitment",
            "economy_wage_terminal_lifecycle",
            "ecology_weather_front_economy_quote_edge",
            "ecology_weather_front_economy_quote_fanout",
            "government_notice_to_social_delivery",
            "action_temporal_consumer_migration",
        "life_state_case_death_caller",
        "population_activation_presence_handoff",
        "population_presence_owner",
        "population_presence_replay_participant",
        "population_economy_random_application_ingress",
        "equipment_command_application_ingress",
        "equipment_prediction_owner_receipt",
        ]
    report = {
        "profile": "infra-admitted-participant-matrix",
        "overall_passed": passed,
        "pytest_output": ((result.stdout or "") + "\n" + (result.stderr or ""))[-6000:],
        "exit_code": result.returncode,
        "focused_tests": tests,
        "evidence": evidence,
        "run_id": f"infra-admitted-participant-matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "participant_count": len(participants),
        "participants": participants,
        "participant_manifest_revision": "stage3-admitted-participants@2026-10-19",
        "contract_shape": {
            "caller": "focused pytest selector listed in focused_tests",
            "owner": "existing domain authority named by the selector/test contract",
            "store": "existing GameplayEventStore or DurableGameplayEventStore; no second store",
            "replay": "only the selector-declared full/checkpoint+tail scope; no global cut implied",
        },
        "global_gate_status": "incomplete",
        "scope": "bounded admitted participant matrix; each path uses its existing owner/store and declared replay scope",
        "limitations": [
            "Includes the fixed Government authored-validity -> Social delivery caller; it does not generalize this path into a generic Social relationship, attendance, or delivery registry.",
            "Does not include Task3 core ResourceEntry, Task4 facility repair/P01-P06, Task5 Soul/Threat/Target, or a global atomic cut.",
            "Presence rows cover the grant-bound application activation handoff, owner and replay participant contracts; a formal scheduler proposal producer and external grant issuer remain unverified.",
            "Economy scheduled transfer and tax rows remain fixed existing owner contracts; this matrix does not generalize them into a prediction ledger or cross-domain settlement.",
        ],
    }
    path = verification_dir(root) / "infra-admitted-participant-matrix-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Admitted Participant Matrix", {"results": [{"id": "admitted-participants", "status": "proved" if passed else "missing", "title": "Bounded admitted caller-owner-store participant paths"}], "overall_passed": passed}, "overall_passed")
    print(f"infra_admitted_participant_matrix_report_json={path}")
    print(f"overall_infra_admitted_participant_matrix_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
