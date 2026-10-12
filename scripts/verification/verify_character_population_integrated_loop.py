from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json


REQUIRED_CASES = (
    "test_two_full_windows_use_public_siming_and_real_owner_core_handoff",
    "test_actual_personal_and_b0_values_match_independent_scalar_oracle",
    "test_reporting_and_duplicate_delivery_do_not_change_authorities",
    "test_budget_defer_restart_can_replay_the_original_personal_window",
    "test_restart_rebuilds_real_core_member_ledger_and_cadence",
    "test_actual_actor_schedule_result_is_consumed_only_with_its_core_receipt",
    "test_player_can_take_over_the_actual_b0_member_without_advancing_other_personal_actors",
    "test_b0_b3_b0_uses_new_member_anchor_and_preserves_identity_after_restart",
    "test_personal_policy_cannot_be_relaxed_by_returning_to_population",
    "test_situation_exit_does_not_reset_personal_state_or_protected_identity",
    "test_confirmed_owner_survives_real_core_refusal_restart_and_redelivery",
    "test_lock_appearing_after_preview_rejects_old_confirmation_without_advancing",
    "test_member_revision_change_at_cadence_append_rejects_before_owner_execution",
    "test_late_first_core_commit_cannot_roll_back_a_newer_confirmed_window",
    "test_delayed_b3_return_uses_own_core_state_and_survives_restart",
    "test_return_of_one_actor_preserves_other_handoff_and_member_results",
    "test_return_failure_can_retry_after_restart_without_losing_other_members",
    "test_committed_reentry_recovers_when_process_state_did_not_receive_ack",
)
TEST_FILES = (
    "test_character_simulation_modules.py", "test_character_population_integrated_loop.py",
    "test_character_population_admission.py", "test_population_flood_cohort.py",
    "test_population_flood_supply_owner.py", "test_population_flood_character_writeback.py",
    "test_population_member_ledger.py", "test_population_handoff_continuity.py",
)


def main() -> int:
    root = repo_root()
    directory = verification_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    junit = directory / "character-population-integrated-loop-junit.xml"
    if junit.exists():
        raise RuntimeError("character_population_integrated_artifact_exists")
    result = run_command([resolve_python_exe(None), "-m", "pytest", "-q", "-p", "no:cacheprovider",
        *(f"backend/tests/{name}" for name in TEST_FILES), f"--junitxml={junit}"], root,
        directory / "character-population-integrated-loop.log")
    clean, checks = False, {name: False for name in REQUIRED_CASES}
    try:
        cases = ET.parse(junit).getroot().findall(".//testcase")
        clean = bool(cases) and all(not list(case) for case in cases)
        passed = {case.get("name", "").split("[", 1)[0] for case in cases if not list(case)}
        checks = {name: name in passed for name in REQUIRED_CASES}
    except (OSError, ET.ParseError):
        pass
    overall = result.returncode == 0 and clean and all(checks.values())
    report = dict(profile="character-population-integrated-loop", overall_passed=overall,
        checks=checks, all_cases_passed=clean, command_exit_code=result.returncode,
        commit=evidence_revision(root), observed_at=datetime.now(timezone.utc).isoformat(),
        evidence=[artifact_ref(root, junit), artifact_ref(root, directory / "character-population-integrated-loop.log")],
        verification_scope="A5_B1_B5_backend_flood_vertical", provider_mode="offline_rules",
        godot_status="paused_by_user", safe_allocation_status="deferred_C3",
        performance_status="separate_population_runtime_scale_gate", active_status="blocked")
    write_json(directory / "character-population-integrated-loop-report.json", report)
    print(f"character_population_integrated_loop_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
