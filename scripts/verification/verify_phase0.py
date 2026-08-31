from __future__ import annotations

import argparse
import os
import sys
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
    wait_for_backend_release,
    verification_dir,
    write_json,
    write_markdown,
)
from runtime_trace import write_runtime_trace

SCENE_LOAD_QUIT_AFTER = "120"
FOCUS_AUTOTEST_QUIT_AFTER = "180"
MAIN_AUTOTEST_MARKER_TIMEOUT_SECONDS = 900.0
FOCUS_AUTOTEST_MARKER_TIMEOUT_SECONDS = 120.0
PHASE0_VERIFY_ENV = {
    "CHARACTER_MODEL_PROVIDER_KIND": "local",
    "CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only",
    "SIMING_HEAVENLY_MODE": "off",
    "SIMING_LLM_MODE": "disabled",
}
PHASE0_PYTEST_TIMEOUT_SECONDS = float(os.environ.get("PHASE0_PYTEST_TIMEOUT_SECONDS", "1200"))
# Phase0's imported throne-hall asset exceeds the available D3D12 test-device
# budget. The compatibility driver preserves scene/script semantics for probes.
PHASE0_GODOT_RENDER_ARGS = ("--rendering-driver", "opengl3")


def _read_character_agent_execution_result(log_dir: Path, project_root: Path, python_exe: str, godot_exe: Path) -> dict[str, object]:
    probe_log = log_dir / "character-agent-execution-from-phase0.log"
    run_command(
        [
            python_exe,
            str(project_root / "scripts" / "verification" / "verify_character_agent_execution.py"),
            "--python-exe",
            python_exe,
            "--godot-exe",
            str(godot_exe),
        ],
        project_root,
        probe_log,
        env=PHASE0_VERIFY_ENV,
    )
    report_path = log_dir / "character-agent-execution-report.json"
    if not report_path.exists():
        return {}
    import json

    return json.loads(report_path.read_text(encoding="utf-8"))


def _read_character_director_observatory_result(log_dir: Path, project_root: Path, python_exe: str, godot_exe: Path) -> dict[str, object]:
    probe_log = log_dir / "character-director-observatory-from-phase0.log"
    run_command(
        [
            python_exe,
            str(project_root / "scripts" / "verification" / "verify_character_director_observatory.py"),
            "--python-exe",
            python_exe,
            "--godot-exe",
            str(godot_exe),
        ],
        project_root,
        probe_log,
    )
    report_path = log_dir / "character-director-observatory-report.json"
    if not report_path.exists():
        return {}
    import json

    return json.loads(report_path.read_text(encoding="utf-8"))


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
    health: dict[str, object] = {}
    try:
        pytest_log = log_dir / "phase0-pytest.log"
        pytest_pythonpath = os.pathsep.join(
            path
            for path in [
                str(project_root),
                str(project_root / "backend"),
                os.environ.get("PYTHONPATH", ""),
            ]
            if path
        )
        pytest_result = run_command(
            [python_exe, "-m", "pytest", "-v", "backend/tests"],
            project_root,
            pytest_log,
            env={"PYTHONPATH": pytest_pythonpath, **PHASE0_VERIFY_ENV},
            timeout_seconds=PHASE0_PYTEST_TIMEOUT_SECONDS,
        )

        health, backend_process = ensure_backend(
            project_root,
            python_exe,
            prefer_fresh_backend=True,
            env=PHASE0_VERIFY_ENV,
        )
        ensure_godot_import(project_root, godot_exe, "phase0-godot-import.log")

        scene_log = log_dir / "phase0-scene-load.log"
        scene_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                *PHASE0_GODOT_RENDER_ARGS,
                "--quit-after",
                SCENE_LOAD_QUIT_AFTER,
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            scene_log,
            env={
                "PHASE0_SCENE_LOAD_ONLY": "1",
            },
        )
        scene_text = read_text(scene_log)
        scene_load_ok = (
            scene_result.returncode == 0
            and "Parse Error" not in scene_text
            and 'Failed to load script "res://scripts/visual/VisualFactEmitter.gd"' not in scene_text
        )

        main_screenshot = log_dir / "phase0-strict-main.png"
        main_log = log_dir / "phase0-main-autotest.log"
        main_result = run_command_until_markers(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                *PHASE0_GODOT_RENDER_ARGS,
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            main_log,
            success_markers=["phase0_autotest_complete"],
            timeout_seconds=MAIN_AUTOTEST_MARKER_TIMEOUT_SECONDS,
            env={
                "PHASE0_AUTOTEST": "1",
                "PHASE0_FOCUS_AUTOTEST": "",
                "PHASE0_AUTOTEST_SCREENSHOT": str(main_screenshot),
            },
        )

        focus_screenshot = log_dir / "phase0-focus-main.png"
        focus_log = log_dir / "phase0-focus-autotest.log"
        focus_result = run_command_until_markers(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                *PHASE0_GODOT_RENDER_ARGS,
                "--quit-after",
                FOCUS_AUTOTEST_QUIT_AFTER,
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            focus_log,
            success_markers=["phase0_focus_autotest_complete"],
            timeout_seconds=FOCUS_AUTOTEST_MARKER_TIMEOUT_SECONDS,
            env={
                "PHASE0_AUTOTEST": "",
                "PHASE0_FOCUS_AUTOTEST": "1",
                "PHASE0_AUTOTEST_SCREENSHOT": str(focus_screenshot),
            },
        )

        main_log_text = read_text(main_log)
        focus_log_text = read_text(focus_log)
        runtime_trace = log_dir / "phase0-runtime-trace.ndjson"
        trace_logs = {"main": main_log_text, "focus": focus_log_text}
        write_runtime_trace(runtime_trace, trace_logs)

        report = evaluate_phase0_audit(
            pytest_passed=pytest_result.returncode == 0,
            scene_load_ok=scene_load_ok,
            main_log=main_log_text,
            focus_log=focus_log_text,
            main_screenshot_exists=main_screenshot.exists() and main_result.returncode == 0,
            focus_screenshot_exists=focus_screenshot.exists() and focus_result.returncode == 0,
            interaction_source=read_text(project_root / "backend" / "app" / "main.py"),
            esm_service_source=read_text(project_root / "backend" / "app" / "services" / "esm_service.py"),
            voice_controller_source=read_text(project_root / "scripts" / "audio" / "SpatialVoiceController.gd"),
            player_bridge_source=read_text(project_root / "scripts" / "player" / "Phase0PlayerBridge.gd"),
            character_replica_source=read_text(project_root / "scripts" / "character" / "CharacterReplica.gd"),
        )
        if backend_process is not None:
            stop_backend(backend_process)
            backend_process = None
        if not wait_for_backend_release():
            raise RuntimeError(
                "Phase 0 backend port 8000 did not fully release before fresh-start child probes."
            )
        execution_probe_report = _read_character_agent_execution_result(log_dir, project_root, python_exe, godot_exe)
        execution_probe_results = execution_probe_report.get("results", []) if isinstance(execution_probe_report, dict) else []
        execution_ids = {
            "character_agent_execution_contract",
            "character_agent_execution_consumer",
        }
        if execution_probe_results:
            report["results"] = [
                existing
                for existing in report["results"]
                if str(existing.get("id", "")) not in execution_ids
            ]
            for entry in execution_probe_results:
                if isinstance(entry, dict) and str(entry.get("id", "")) in execution_ids:
                    report["results"].append(entry)
        observatory_probe_report = _read_character_director_observatory_result(log_dir, project_root, python_exe, godot_exe)
        observatory_probe_results = observatory_probe_report.get("results", []) if isinstance(observatory_probe_report, dict) else []
        observatory_ids = {
            "observatory_state_payloads",
            "observatory_panels_populated",
            "observatory_actor_panel_populated",
            "observatory_director_workstation_populated",
            "observatory_selected_actor_siming_summary",
            "observatory_bottom_strip_siming",
            "observatory_timeline_multi_role",
            "observatory_timeline_siming",
            "observatory_ledger_pairwise",
            "observatory_ledger_siming_pressure",
            "observatory_freeze_roundtrip",
        }
        if observatory_probe_results:
            report["results"] = [
                existing
                for existing in report["results"]
                if str(existing.get("id", "")) not in observatory_ids
            ]
            for entry in observatory_probe_results:
                if isinstance(entry, dict) and str(entry.get("id", "")) in observatory_ids:
                    report["results"].append(entry)
        strict_ids = [
            "backend_tests",
            "scene_load",
            "backend_connectivity",
            "dialogue_loop",
            "successful_interaction",
            "failed_interaction",
            "visible_world_state_change",
            "esm_request_lineage",
            "esm_thermal_field",
            "siming_reaction",
            "voice_stub_path",
            "player_root_motion_chain",
            "npc_root_motion_patrol",
            "locomotion_state_ui",
            "jump_variant_probes",
            "forward_direction_probe",
            "repeatable_run",
            "observatory_state_payloads",
            "observatory_panels_populated",
            "observatory_actor_panel_populated",
            "observatory_director_workstation_populated",
            "observatory_selected_actor_siming_summary",
            "observatory_bottom_strip_siming",
            "observatory_timeline_multi_role",
            "observatory_timeline_siming",
            "observatory_ledger_pairwise",
            "observatory_ledger_siming_pressure",
            "observatory_freeze_roundtrip",
        ]
        index = {str(entry["id"]): str(entry["status"]) for entry in report["results"]}
        report["overall_strict_phase0_passed"] = all(index.get(result_id) == "proved" for result_id in strict_ids)
        report["backend_health"] = health
        report["artifacts"] = {
            "pytest_log": str(pytest_log),
            "scene_log": str(scene_log),
            "main_log": str(main_log),
            "focus_log": str(focus_log),
            "main_screenshot": str(main_screenshot),
            "focus_screenshot": str(focus_screenshot),
            "runtime_trace": str(runtime_trace),
            "character_agent_execution_report": str(log_dir / "character-agent-execution-report.json"),
            "character_director_observatory_report": str(log_dir / "character-director-observatory-report.json"),
        }

        json_path = log_dir / "phase0-report.json"
        md_path = log_dir / "phase0-report.md"
        write_json(json_path, report)
        write_markdown(md_path, "Phase 0 Verification Report", report, "overall_strict_phase0_passed")

        print(f"phase0_report_json={json_path}")
        print(f"phase0_report_md={md_path}")
        print(f"overall_strict_phase0_passed={report['overall_strict_phase0_passed']}")
        for entry in report["results"]:
            print(f"{entry['id']}={entry['status']}")
        return 0 if report["overall_strict_phase0_passed"] else 1
    finally:
        stop_backend(backend_process)


if __name__ == "__main__":
    exit_code = main()
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    finally:
        os._exit(exit_code)
