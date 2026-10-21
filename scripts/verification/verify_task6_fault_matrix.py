from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    tests = [
        root / "backend/tests/test_world_admin_auth_service.py",
        root / "backend/tests/test_world_admin_cadence_revocation_application.py",
        root / "backend/tests/test_runtime_asgi.py::test_bootstrap_preserves_excluded_settings_and_real_http_enrollment",
        root / "backend/tests/test_runtime_asgi.py::test_actual_asgi_http_dispatches_original_typed_route_on_child_owner",
        root / "backend/tests/test_task6_fault_matrix.py",
        root / "backend/tests/test_resource_replay_participant.py",
        root / "backend/tests/test_economy_random_replay_participant.py",
        root / "backend/tests/test_life_state_replay_participant.py",
        root / "backend/tests/test_equipment_replay_participant.py",
        root / "backend/tests/test_inventory_replay_participant.py",
        root / "backend/tests/test_equipment_runtime.py",
        root / "backend/tests/test_world_replay_checkpoint_application.py",
        root / "backend/tests/test_p5_social_knowledge.py",
        root / "backend/tests/test_p5_social_delivery.py",
        root / "backend/tests/test_world_replay_checkpoint_cut.py",
        root / "backend/tests/test_world_replay_participants.py",
        root / "backend/tests/test_resource_recovery.py",
        root / "backend/tests/test_resource_modifier_admission.py",
        root / "backend/tests/test_street_combat_durable_owner.py",
        root / "backend/tests/test_equipment_stage3_recovery.py",
        root / "backend/tests/test_world_prediction.py",
        root / "backend/tests/test_economy_due_calendar_caller.py",
        root / "backend/tests/test_population_economy_random_caller.py",
        root / "backend/tests/test_population_economy_random_application.py",
        root / "backend/tests/test_economy_random_owner.py",
        root / "backend/tests/test_economy_random_registry.py",
        root / "backend/tests/test_economy_random_command_service.py",
        root / "backend/tests/test_economy_random_command_application.py",
        root / "backend/tests/test_equipment_command_service.py",
        root / "backend/tests/test_equipment_command_application.py",
        root / "backend/tests/test_equipment_prediction_service.py",
        root / "backend/tests/test_population_activation_presence_service.py",
        root / "backend/tests/test_life_state_case_death_caller.py",
    ]
    log = Path(tempfile.gettempdir()) / "paralls-task6-fault-matrix.log"
    result = run_command([resolve_python_exe(None), "-m", "pytest", "-q", *map(str, tests)], root, log, timeout_seconds=1500)
    passed = result.returncode == 0
    log.unlink(missing_ok=True)
    report = {
        "profile": "infra-task6-fault-matrix",
        "overall_passed": passed,
        "run_id": f"infra-task6-fault-matrix-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "revision": evidence_revision(root),
        "focused_tests": [str(test.relative_to(root)).replace("\\", "/") for test in tests],
        "matrix": {
            "exact_duplicate": "proved",
            "changed_duplicate": "proved",
            "lost_response": "proved_by_receipt_replay",
            "partial_success": "proved_activation_presence_retry",
            "expired_revoked": "proved_facility_fail_closed",
            "revision_conflict": "proved_migration_zero_write",
            "migration_failure": "proved_overlap_rejection",
            "durable_new_instance": "proved",
            "full_checkpoint_tail": "proved",
            "street_owner_durable_new_instance": "proved_exact_duplicate_changed_duplicate_append_failure_zero_write",
            "equipment_prediction_owner_receipt": "proved_durable_reopen_owner_principal_receipt_confirmation_and_checkpoint_tail",
            "economy_due_calendar": "proved_population_cadence_calendar_revalidation_tax_owner_receipt_and_durable_reopen",
            "economy_random": "proved_population_random_caller_owner_seed_result_receipt_and_durable_replay",
            "world_batch_recovery": "proved_partial_commit_durable_reopen_new_adapters_receipt_replay_without_duplicate_events",
            "same_durable_cut_mixed_owner_replay": "proved_batch_and_resource_owner_events_share_one_cut_full_equals_checkpoint_tail",
            "resource_domain_participant": "proved_saved_resource_checkpoint_tail_full_parity_after_durable_reopen_and_corruption_zero_write",
            "equipment_domain_participant": "proved_active_domain_checkpoint_unequip_tail_full_parity_after_durable_reopen_and_corruption_zero_write",
            "inventory_domain_participant": "proved_items_containers_reservations_capacity_checkpoint_tail_full_parity_after_durable_reopen_and_corruption_zero_write",
            "life_state_participant": "proved_alive_checkpoint_dead_tail_full_parity_after_durable_reopen_and_corruption_zero_write",
            "social_fact_provenance": "proved_stream_visibility_schema_owner_transaction_and_persisted_event_rejection_zero_write",
            "social_delivery_provenance": "proved_recipient_stream_visibility_schema_owner_transaction_and_persisted_event_rejection_zero_write",
            "world_admin_cadence_revocation": "proved_configured_spawn_http_owner_receipt_restart_and_execution_time_auth_revalidation_zero_write",
        },
        "scope": "bounded real slices: resource recovery, population activation/presence, facility repair admission, resource migration control, existing street owner durable receipt recovery, Equipment owner receipt confirmation, and world batch partial-commit recovery",
        "limitations": [
            "Not a global all-owner fault cut; Task1–Task5 owners remain bounded independently evidenced slices.",
            "Resource migration replay requires historical definitions not yet assembled by the application; missing definitions fail closed.",
            "Equipment participant preserves ability/modifier/container references; their independent domain projections are not reconstructed by it.",
            "Inventory domain participant covers its existing projection fields; commerce custody/delivery event effects outside that projector remain separately owned.",
            "Social delivery multi-recipient owner-direct replay does not prove a production Government multi-recipient demand caller.",
            "World-admin evidence uses configured test service accounts and ASGI schemes; deployed credentials, real TLS and broader grant issuers remain unverified. Facility repair execution remains deferred.",
        ],
        "exit_code": result.returncode,
        "pytest_output": ((result.stdout or "") + "\n" + (result.stderr or ""))[-6000:],
    }
    if not passed:
        report["matrix"] = {key: "not_verified_suite_failed" for key in report["matrix"]}
    path = verification_dir(root) / "infra-task6-fault-matrix-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Task6 Bounded Fault Matrix", {
        "results": [{"id": key, "status": value, "title": key.replace("_", " ")} for key, value in report["matrix"].items()],
        "overall_passed": passed,
        "limitations": report["limitations"],
    }, "overall_passed")
    print(f"task6_fault_matrix_report_json={path}")
    print(f"overall_task6_fault_matrix_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope
    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
