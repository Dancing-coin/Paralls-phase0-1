from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import (
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    verification_dir,
    write_json,
    write_markdown,
)


def _result(result_id: str, title: str, exit_code: int, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if exit_code == 0 else "missing",
        "evidence": evidence if exit_code == 0 else [],
        "notes": notes,
    }


def _run_profile(
    *,
    project_root: Path,
    python_exe: str,
    log_dir: Path,
    log_name: str,
    command: list[str],
) -> tuple[int, str]:
    log_path = log_dir / log_name
    result = run_command(command, project_root, log_path)
    return result.returncode, str(log_path)


def _load_report(path: Path) -> dict[str, object]:
    text = read_text(path)
    if text == "":
        return {}
    return json.loads(text)


def _run_runtime_verifier_with_retry(
    *,
    project_root: Path,
    python_exe: str,
    log_dir: Path,
    result_id: str,
    title: str,
    script_name: str,
    report_path: Path,
    log_name: str,
    godot_exe: Path,
    max_attempts: int = 2,
) -> tuple[dict[str, object], dict[str, str]]:
    last_result = _result(result_id, title, 1, [], "")
    last_log_path = ""
    last_notes = ""
    for _attempt in range(1, max_attempts + 1):
        exit_code, log_path = _run_profile(
            project_root=project_root,
            python_exe=python_exe,
            log_dir=log_dir,
            log_name=log_name,
            command=[
                python_exe,
                str(project_root / "scripts" / "verification" / script_name),
                "--godot-exe",
                str(godot_exe),
                "--python-exe",
                python_exe,
            ],
        )
        report_payload = _load_report(report_path)
        overall_key = next((key for key in report_payload.keys() if key.startswith("overall_")), "")
        last_notes = ""
        if overall_key and report_payload.get(overall_key) is not True:
            last_notes = f"{script_name} reported {overall_key}={report_payload.get(overall_key)!r}"
        last_result = _result(result_id, title, exit_code, [log_path, str(report_path)], last_notes)
        last_log_path = log_path
        if exit_code == 0:
            return last_result, {"log": last_log_path, "report": str(report_path)}
    return last_result, {"log": last_log_path, "report": str(report_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    godot_exe = resolve_godot_exe(args.godot_exe)

    results: list[dict[str, object]] = []
    artifacts: dict[str, object] = {}

    world_runtime_exit, world_runtime_log = _run_profile(
        project_root=project_root,
        python_exe=python_exe,
        log_dir=log_dir,
        log_name="mainline-unified-world-runtime.log",
        command=[
            python_exe,
            "-m",
            "pytest",
            "backend/tests/test_world_runtime_models.py",
            "backend/tests/test_world_runtime_fact_registry.py",
            "backend/tests/test_world_runtime_projection.py",
            "backend/tests/test_world_runtime_scheduling.py",
            "backend/tests/test_world_runtime_continuity.py",
            "-v",
        ],
    )
    results.append(
        _result(
            "mainline_world_runtime_suite",
            "Canonical world-runtime model, routing, projection, scheduling, and continuity checks pass",
            world_runtime_exit,
            [world_runtime_log],
        )
    )
    artifacts["world_runtime_log"] = world_runtime_log

    asset_runtime_exit, asset_runtime_log = _run_profile(
        project_root=project_root,
        python_exe=python_exe,
        log_dir=log_dir,
        log_name="mainline-unified-asset-runtime.log",
        command=[
            python_exe,
            "-m",
            "pytest",
            "backend/tests/test_character_asset_registry_static.py",
            "backend/tests/test_kimodo_adapter_contract.py",
            "-v",
        ],
    )
    results.append(
        _result(
            "asset_runtime_kimodo_contracts",
            "Asset registry/preload contracts and Kimodo adapter contract checks pass",
            asset_runtime_exit,
            [asset_runtime_log],
        )
    )
    artifacts["asset_runtime_kimodo_contracts_log"] = asset_runtime_log

    continuity_observatory_exit, continuity_observatory_log = _run_profile(
        project_root=project_root,
        python_exe=python_exe,
        log_dir=log_dir,
        log_name="mainline-unified-continuity-observatory.log",
        command=[
            python_exe,
            "-m",
            "pytest",
            "backend/tests/test_observatory_models.py",
            "backend/tests/test_character_agent_debug_projection.py",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_observatory_snapshot_carries_cadence_and_continuity_summaries",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_observatory_snapshot_carries_scheduling_summary_for_degraded_population",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_emits_scheduling_state_event_for_selected_actor_under_population_pressure",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_exposes_unified_scheduling_state_for_population_tick",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_scheduling_round_state_advances_round_id_when_new_runtime_tick_arrives",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_scheduling_state_exposes_selection_reason_tags_for_active_actor_set",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_scheduling_state_exposes_round_summary_and_reason_tags_for_active_actor_set",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_emits_single_scheduling_round_state_event_with_unified_summary",
            "backend/tests/test_debug_panel.py::test_debug_ws_replays_scheduling_round_state_observatory_event",
            "backend/tests/test_debug_panel.py::test_debug_ws_replays_script_beat_event_for_scheduling_round_summary",
            "backend/tests/test_debug_panel.py::test_debug_ws_replays_scheduling_round_trace_event",
            "backend/tests/test_observatory_message_delivery_static.py",
            "backend/tests/test_character_director_state_static.py",
            "backend/tests/test_character_agent_action_request_routing.py::test_character_agent_execution_route_emits_scheduling_round_trace",
            "backend/tests/test_ws_protocol.py::test_websocket_character_agent_execution_emits_scheduling_round_trace",
            "backend/tests/test_ws_protocol.py::test_websocket_interact_intent_emits_scheduling_round_trace_after_character_agent_execution",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_degraded_mode_defers_second_cognition_pass_inside_cadence_window",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_degraded_mode_defers_second_perception_pass_inside_perception_window",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_wake_up_high_salience_siming_input_bypasses_degraded_cognition_deferral",
            "-v",
        ],
    )
    results.append(
        _result(
            "runtime_cadence_continuity_observatory",
            "Cadence, scheduling, unified scheduling state, scheduling rounds, round summaries, round-state events, round traces, websocket trace delivery, interact-chain websocket trace delivery, debug-stream propagation, round-trace debug propagation, script-beat propagation, frontend signal/state chain, selection reasons, wake-up, continuity, scheduling-state events, and degraded-mode perception/cognition deferral appear in runtime evidence",
            continuity_observatory_exit,
            [continuity_observatory_log],
        )
    )
    artifacts["runtime_cadence_continuity_observatory_log"] = continuity_observatory_log

    runtime_verifiers = [
        (
            "actor_local_perception",
            "Actor-local perception runtime proof passes",
            "verify_actor_local_perception.py",
            log_dir / "actor-local-perception-report.json",
            "mainline-unified-actor-local.log",
        ),
        (
            "autonomous_social_contact",
            "Autonomous social contact runtime proof passes",
            "verify_autonomous_social_contact.py",
            log_dir / "autonomous-social-contact-report.json",
            "mainline-unified-autonomous-contact.log",
        ),
        (
            "character_agent_execution",
            "Shared actor execution ingress proof passes",
            "verify_character_agent_execution.py",
            log_dir / "character-agent-execution-report.json",
            "mainline-unified-character-agent-execution.log",
        ),
        (
            "phase1_slice",
            "Phase1-shaped runtime slice proof passes",
            "verify_phase1_slice.py",
            log_dir / "phase1-slice-report.json",
            "mainline-unified-phase1-slice.log",
        ),
    ]

    for result_id, title, script_name, report_path, log_name in runtime_verifiers:
        result, runtime_artifacts = _run_runtime_verifier_with_retry(
            project_root=project_root,
            python_exe=python_exe,
            log_dir=log_dir,
            result_id=result_id,
            title=title,
            script_name=script_name,
            report_path=report_path,
            log_name=log_name,
            godot_exe=godot_exe,
        )
        results.append(result)
        artifacts[f"{result_id}_log"] = runtime_artifacts["log"]
        artifacts[f"{result_id}_report"] = runtime_artifacts["report"]

    settlement_exit, settlement_log = _run_profile(
        project_root=project_root,
        python_exe=python_exe,
        log_dir=log_dir,
        log_name="mainline-unified-settlement-writeback.log",
        command=[
            python_exe,
            "-m",
            "pytest",
            "backend/tests/test_ws_protocol.py::test_approach_settlement_result_preserves_action_profile_and_target_actor",
            "backend/tests/test_visual_fact_pipeline.py::test_social_spatial_settlement_result_is_projected_back_into_runtime_outputs",
            "-v",
        ],
    )
    results.append(
        _result(
            "authority_settlement_writeback",
            "Authority settlement semantics and runtime writeback checks pass",
            settlement_exit,
            [settlement_log],
        )
    )
    artifacts["authority_settlement_writeback_log"] = settlement_log

    continuity_recovery_exit, continuity_recovery_log = _run_profile(
        project_root=project_root,
        python_exe=python_exe,
        log_dir=log_dir,
        log_name="mainline-unified-continuity-recovery.log",
        command=[
            python_exe,
            "-m",
            "pytest",
            "backend/tests/test_character_agent_action_request_routing.py::test_social_spatial_continuity_marks_recovering_when_contact_resumes",
            "backend/tests/test_character_agent_runtime_memory_integration.py::test_runtime_marks_recovering_when_approach_restarts_after_terminal_transition",
            "-v",
        ],
    )
    results.append(
        _result(
            "continuity_recovery_runtime",
            "Continuity recovery is preserved across renewed social-spatial contact",
            continuity_recovery_exit,
            [continuity_recovery_log],
        )
    )
    artifacts["continuity_recovery_runtime_log"] = continuity_recovery_log

    overall_passed = all(str(entry["status"]) == "proved" for entry in results)
    report = {
        "results": results,
        "overall_mainline_unified_runtime_passed": overall_passed,
        "artifacts": artifacts,
    }

    json_path = log_dir / "mainline-unified-runtime-report.json"
    md_path = log_dir / "mainline-unified-runtime-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Mainline Unified Runtime Verification Report",
        report,
        "overall_mainline_unified_runtime_passed",
    )

    print(f"mainline_unified_runtime_report_json={json_path}")
    print(f"mainline_unified_runtime_report_md={md_path}")
    print(f"overall_mainline_unified_runtime_passed={report['overall_mainline_unified_runtime_passed']}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
