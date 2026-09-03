from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.verification_audit import evaluate_phase0_audit

from common import (
    ensure_godot_import,
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    run_command_until_markers,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)
from runtime_trace import write_runtime_trace

EXECUTION_PROBE_QUIT_AFTER = "240"
EXECUTION_PROBE_MARKER_TIMEOUT_SECONDS = 90.0
EXECUTION_PAYLOAD_DIRECT_MARKER = "character_agent_execution_probe:execution_payload_direct=true"
CONSUMER_SEEN_MARKER = "character_agent_execution_probe:consumer_seen=true"
LEGACY_OUTPUT_CLEAR_MARKER = "character_agent_execution_probe:legacy_output_seen=false"
ALL_CHECKS_COMPLETE_MARKER = "character_agent_execution_probe:all_checks_complete=true"
CHARACTER_EXECUTION_VERIFY_ENV = {
    "CHARACTER_MODEL_PROVIDER_KIND": "local",
    "CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    godot_exe = resolve_godot_exe(args.godot_exe)
    python_exe = resolve_python_exe(args.python_exe)

    backend_process = None
    graph_temp_dir = tempfile.mkdtemp(prefix="character-agent-execution-graph-", dir=str(log_dir))
    execution_env = dict(CHARACTER_EXECUTION_VERIFY_ENV)
    execution_env["PARALLS_HEAVENLY_GRAPH_PATH"] = str(Path(graph_temp_dir) / "siming-heavenly.sqlite3")
    try:
        health, backend_process = ensure_backend(
            project_root,
            python_exe,
            prefer_fresh_backend=True,
            env=execution_env,
        )
        ensure_godot_import(project_root, godot_exe, "character-agent-execution-godot-import.log")

        main_screenshot = log_dir / "character-agent-execution-main.png"
        main_log = log_dir / "character-agent-execution-main.log"
        main_result = run_command_until_markers(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/CharacterAgentExecutionProbe.tscn",
                "--quit-after",
                EXECUTION_PROBE_QUIT_AFTER,
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            main_log,
            success_markers=[
                ALL_CHECKS_COMPLETE_MARKER,
            ],
            timeout_seconds=EXECUTION_PROBE_MARKER_TIMEOUT_SECONDS,
            env={
                "PHASE0_AUTOTEST_SCREENSHOT": str(main_screenshot),
                "PHASE0_DEBUG_LOGGING": "1",
                "CHARACTER_MODEL_PROVIDER_KIND": "local",
                "CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only",
                "PARALLS_HEAVENLY_GRAPH_PATH": execution_env["PARALLS_HEAVENLY_GRAPH_PATH"],
            },
        )

        main_log_text = read_text(main_log)
        runtime_trace = log_dir / "character-agent-execution-runtime-trace.ndjson"
        write_runtime_trace(runtime_trace, {"main": main_log_text})

        phase0_report = evaluate_phase0_audit(
            pytest_passed=False,
            scene_load_ok=True,
            main_log=main_log_text,
            focus_log="",
            main_screenshot_exists=main_screenshot.exists() and main_result.returncode == 0,
            focus_screenshot_exists=True,
            interaction_source=read_text(project_root / "backend" / "app" / "main.py"),
            esm_service_source=read_text(project_root / "backend" / "app" / "services" / "esm_service.py"),
            voice_controller_source=read_text(project_root / "scripts" / "audio" / "SpatialVoiceController.gd"),
            player_bridge_source=read_text(project_root / "scripts" / "player" / "Phase0PlayerBridge.gd"),
            character_replica_source=read_text(project_root / "scripts" / "character" / "CharacterReplica.gd"),
        )
        execution_entry = next(
            entry for entry in phase0_report["results"] if entry["id"] == "character_agent_execution_contract"
        )
        execution_payload_direct_ok = EXECUTION_PAYLOAD_DIRECT_MARKER in main_log_text
        if execution_entry["status"] == "proved" and execution_payload_direct_ok:
            execution_entry["evidence"].append("execution_payload_direct")
        elif execution_entry["status"] == "proved":
            execution_entry["status"] = "missing"
            execution_entry["evidence"] = []
            execution_entry["notes"] = (
                "Probe did not confirm the received execution payload directly carried "
                "actor_control_frames/presentation_plan/action_request_bundle."
            )
        consumer_ok = (
            CONSUMER_SEEN_MARKER in main_log_text
            and LEGACY_OUTPUT_CLEAR_MARKER in main_log_text
        )
        consumer_entry = {
            "id": "character_agent_execution_consumer",
            "title": "Shared actor runtime consumes the execution contract",
            "status": "proved" if consumer_ok else "missing",
            "evidence": ["character_agent_execution_applied", CONSUMER_SEEN_MARKER]
            if consumer_ok
            else [],
            "notes": "" if consumer_ok else "Probe did not confirm the shared actor runtime consumed the execution contract and applied it.",
        }
        overall_passed = (
            execution_entry["status"] == "proved"
            and consumer_entry["status"] == "proved"
        )
        report = {
            "results": [execution_entry, consumer_entry],
            "overall_character_agent_execution_passed": overall_passed,
            "backend_health": health,
            "artifacts": {
                "main_log": str(main_log),
                "main_screenshot": str(main_screenshot),
                "runtime_trace": str(runtime_trace),
            },
        }

        json_path = log_dir / "character-agent-execution-report.json"
        md_path = log_dir / "character-agent-execution-report.md"
        write_json(json_path, report)
        write_markdown(
            md_path,
            "Character Agent Execution Verification Report",
            report,
            "overall_character_agent_execution_passed",
        )

        print(f"character_agent_execution_report_json={json_path}")
        print(f"character_agent_execution_report_md={md_path}")
        print(f"overall_character_agent_execution_passed={report['overall_character_agent_execution_passed']}")
        print(f"{execution_entry['id']}={execution_entry['status']}")
        print(f"{consumer_entry['id']}={consumer_entry['status']}")
        return 0 if overall_passed else 1
    finally:
        stop_backend(backend_process)
        shutil.rmtree(graph_temp_dir, ignore_errors=True)


if __name__ == "__main__":
    exit_code = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(exit_code)
