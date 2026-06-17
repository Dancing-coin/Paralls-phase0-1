from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.verification_audit import evaluate_phase0_audit

from common import (
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)
from runtime_trace import write_runtime_trace


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
    )
    report_path = log_dir / "character-agent-execution-report.json"
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
    try:
        health, backend_process = ensure_backend(project_root, python_exe, prefer_fresh_backend=True)

        pytest_log = log_dir / "phase0-pytest.log"
        pytest_result = run_command([python_exe, "-m", "pytest", "-v"], project_root / "backend", pytest_log)

        scene_log = log_dir / "phase0-scene-load.log"
        scene_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                "--quit-after",
                "1800",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            scene_log,
            env={
                "PHASE0_DEBUG_LOGGING": "1",
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
        main_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                "--quit-after",
                "1800",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            main_log,
            env={
                "PHASE0_AUTOTEST": "1",
                "PHASE0_FOCUS_AUTOTEST": "",
                "PHASE0_AUTOTEST_SCREENSHOT": str(main_screenshot),
                "PHASE0_DEBUG_LOGGING": "1",
            },
        )

        focus_screenshot = log_dir / "phase0-focus-main.png"
        focus_log = log_dir / "phase0-focus-autotest.log"
        focus_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/MainDemo.tscn",
                "--quit-after",
                "1800",
                "--verbose",
                "--render-thread",
                "safe",
            ],
            project_root,
            focus_log,
            env={
                "PHASE0_AUTOTEST": "",
                "PHASE0_FOCUS_AUTOTEST": "1",
                "PHASE0_AUTOTEST_SCREENSHOT": str(focus_screenshot),
                "PHASE0_DEBUG_LOGGING": "1",
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
        execution_probe_report = _read_character_agent_execution_result(log_dir, project_root, python_exe, godot_exe)
        execution_probe_results = execution_probe_report.get("results", []) if isinstance(execution_probe_report, dict) else []
        for entry in execution_probe_results:
            if isinstance(entry, dict) and str(entry.get("id", "")) == "character_agent_execution_consumer":
                report["results"] = [
                    existing
                    for existing in report["results"]
                    if str(existing.get("id", "")) != "character_agent_execution_consumer"
                ]
                report["results"].append(entry)
                break
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
    raise SystemExit(main())
