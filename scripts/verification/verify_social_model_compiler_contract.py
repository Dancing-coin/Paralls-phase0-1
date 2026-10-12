from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json


REQUIRED_CASES = (
    "test_unknown_templates_code_and_request_facts_are_rejected",
    "test_grant_cannot_expand_scope_time_or_budget",
    "test_model_copy_cannot_bypass_run_admission",
    "test_card_readset_cannot_omit_a_real_source_dependency",
    "test_frozen_input_copies_nested_content_and_serialization",
    "test_card_order_and_mapping_order_preserve_input_digest",
    "test_changed_observation_is_a_different_input_even_if_streams_are_identical",
    "test_missing_historical_content_does_not_fall_back_to_current",
    "test_unknown_or_known_closed_route_cannot_report_positive_reachability",
    "test_failure_receipt_records_pins_without_fact_bodies_or_fake_output",
    "test_standard_bounds_are_deterministic_and_read_only",
    "test_budget_exhaustion_never_returns_partial_report",
    "test_off_does_not_read_model_sources_or_expose_report",
    "test_shadow_is_audit_only_while_advisory_exposes_the_same_pure_report",
    "test_every_source_pin_is_rechecked_before_model_exposure",
    "test_revocation_during_source_read_cannot_expose_advisory",
    "test_real_owner_gap_never_invents_route_process_or_shard_facts",
    "test_public_siming_observer_cannot_add_owner_core_or_handoff_work",
)


def main() -> int:
    root = repo_root()
    directory = verification_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    junit = directory / "social-model-compiler-contract-junit.xml"
    # 本次执行必须生成新结果，不允许读取同一 scope 留下的旧 JUnit。
    if junit.exists():
        raise RuntimeError("social_model_contract_artifact_exists")
    command = [resolve_python_exe(None), "-m", "pytest", "-q", "-p", "no:cacheprovider",
        "backend/tests/test_social_model_execution_contract.py", "backend/tests/test_social_model_replay.py",
        "backend/tests/test_daily_supply_calculator.py", "backend/tests/test_daily_supply_shadow_comparison.py",
        f"--junitxml={junit}"]
    result = run_command(command, root, directory / "social-model-compiler-contract.log")
    checks = {name: False for name in REQUIRED_CASES}
    clean = False
    try:
        cases = ET.parse(junit).getroot().findall(".//testcase")
        clean = bool(cases) and all(not list(case) for case in cases)
        passed = {case.get("name", "").split("[", 1)[0] for case in cases if not list(case)}
        checks = {name: name in passed for name in REQUIRED_CASES}
    except (OSError, ET.ParseError):
        pass
    overall = result.returncode == 0 and clean and all(checks.values())
    report = dict(profile="social-model-compiler-contract", overall_passed=overall,
        checks=checks, command_exit_code=result.returncode, all_cases_passed=clean,
        commit=evidence_revision(root), observed_at=datetime.now(timezone.utc).isoformat(),
        evidence=[artifact_ref(root, junit), artifact_ref(root, directory / "social-model-compiler-contract.log")],
        verification_scope="AM1_BM1_pure_calculation_and_readonly_mode_boundaries",
        bm1_calculator_status="verified" if overall else "verification_failed",
        hm0_status="pure_calculator_verified" if overall else "verification_failed",
        shadow_status="blocked_live_source_contract", advisory_status="blocked_live_source_contract",
        mode_boundary_status="verified" if overall else "verification_failed",
        missing_live_dependencies=["route", "supply_process", "commitment_priority", "complete_shard_membership",
            "production_model_run_grant_issuer"],
        active_status="blocked", performance_status="not_run", godot_status="paused_by_user")
    write_json(directory / "social-model-compiler-contract-report.json", report)
    print(f"social_model_compiler_contract_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
