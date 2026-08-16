from __future__ import annotations

from datetime import datetime, timezone

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    focused = root / "backend" / "tests" / "test_infra_population_world_mode_complete.py"
    branch = root / "backend" / "tests" / "test_infra_population_branch_preview.py"
    cases = {
        "world_plan_base_tail_budget": (focused, "test_inf4z_world_plan_pins_base_tail_revisions_and_budget"),
        "game_mode_cadence_budget": (focused, "test_inf4z_game_mode_preserves_caller_selected_interactive_budget"),
        "simulation_mode_cadence_budget": (focused, "test_inf4z_simulation_mode_preserves_caller_selected_daily_budget"),
        "preview_mode_cadence_budget": (focused, "test_inf4z_preview_mode_preserves_caller_selected_fixed_base_budget"),
        "preview_production_zero_write": (focused, "test_inf4z_preview_world_plan_is_zero_write_at_production_merge_boundary"),
        "existing_owner_supply_fragment_receipt": (focused, "test_inf4z_supply_uses_existing_organization_owner_fragment_and_receipt"),
        "existing_owner_inspection_fragment_receipt": (focused, "test_inf4z_inspection_uses_existing_government_owner_fragment_and_receipt"),
        "inspection_scoped_outbox_privacy_replay": (focused, "test_inf4z_inspection_writes_redacted_scoped_outbox_projection"),
        "unsupported_work_zero_write": (focused, "test_inf4z_unmapped_work_intent_is_zero_write"),
        "legacy_population_merge_zero_write": (focused, "test_inf4z_legacy_population_merge_cannot_write_free_form_stream_or_event"),
        "duplicate_idempotency": (focused, "test_inf4z_supply_duplicate_idempotency_replays_existing_owner_receipt"),
        "revision_conflict_zero_write": (focused, "test_inf4z_supply_revision_conflict_is_zero_write"),
        "privacy_scope_zero_write": (focused, "test_inf4z_supply_privacy_scope_denial_is_zero_write"),
        "activation_lock_pending_zero_write": (focused, "test_inf4z_activation_lock_pending_is_zero_write"),
        "production_full_checkpoint_tail_replay": (focused, "test_inf4z_supply_production_full_and_checkpoint_tail_replay_match"),
        "branch_source_digest_pin": (focused, "test_inf4z_branch_request_pins_tail_and_source_digests"),
        "fixed_base_branch_replay": (branch, "test_fixed_base_branch_replay_pins_checkpoint_tail_and_source_digests"),
        "branch_tail_zero_write": (branch, "test_fixed_base_branch_rejects_tail_beyond_production_without_writes"),
    }
    checks: dict[str, bool] = {}
    evidence: list[str] = []
    for check, (test_path, test_name) in cases.items():
        log_path = verification_dir(root) / f"infra-population-world-mode-complete-{check}.log"
        result = run_command([python, "-m", "pytest", "-q", str(test_path), "-k", test_name], root, log_path)
        checks[check] = result.returncode == 0
        evidence.append(str(log_path.relative_to(root)).replace("\\", "/"))
    report = {
        "profile": "infra-population-world-mode-complete",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "focused_test_files": [str(focused.relative_to(root)).replace("\\", "/"), str(branch.relative_to(root)).replace("\\", "/")],
        "evidence": evidence,
        "run_id": f"infra-population-world-mode-complete-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owners": ["actor_gameplay.organization_domain", "actor_gameplay.government_domain", "backend/app/population_continuity/branch_preview.py"],
        "streams": ["gameplay:organization:{organization_ref}", "gameplay:government:{organization_ref}"],
        "event_types": ["gameplay.organization.commerce_commitment_accepted", "gameplay.government.inspection_recorded"],
        "write_path": "PopulationWorldPlan -> existing Organization/Government owner fragment -> GameplayCommandEnvelope/SettlementPlan -> GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "limitations": [
            "Only supply and inspection intents are admitted through existing domain owner fragments.",
            "work intent mapping and the retired legacy PopulationBatchPlan merge remain zero-write.",
            "No population truth owner, scheduler, clock, branch promotion, civilization consumer, P6 or P7 is created.",
        ],
    }
    path = verification_dir(root) / "infra-population-world-mode-complete-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "INF-4Z Bounded Population World-Mode Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"infra_population_world_mode_complete_report_json={path}")
    print(f"overall_infra_population_world_mode_complete_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
