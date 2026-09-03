from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from common import run_command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", required=True)
    parser.add_argument("--python-exe")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    scene = root / "scenes" / "phase0" / "ProceduralConstructionEditor.tscn"
    command = [
        args.godot_exe,
        "--headless",
        "--path",
        str(root),
        "--scene",
        "res://scenes/phase0/ProceduralConstructionEditorRuntimeProbe.tscn",
    ]
    log_path = root / ".harness" / "verification" / "procedural-construction-editor-runtime.log"
    completed = run_command(command, root, log_path, timeout_seconds=30)
    timed_out = completed.returncode == 124
    desktop_log_path = root / ".harness" / "verification" / "procedural-construction-editor-desktop-runtime.log"
    desktop_command = [
        args.godot_exe,
        "--path",
        str(root),
        "--scene",
        "res://scenes/phase0/ProceduralConstructionEditorRuntimeProbe.tscn",
        "--quit-after",
        "2",
    ]
    desktop_completed = run_command(desktop_command, root, desktop_log_path, timeout_seconds=30)
    desktop_timed_out = desktop_completed.returncode == 124
    passed = (
        scene.exists()
        and not timed_out
        and completed.returncode == 0
        and not desktop_timed_out
        and desktop_completed.returncode == 0
    )
    report = {
        "profile": "procedural-construction-editor-runtime",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "godot_exe": args.godot_exe,
        "scene": "res://scenes/phase0/ProceduralConstructionEditor.tscn",
        "command": command,
        "desktop_command": desktop_command,
        "scene_exists": scene.exists(),
        "timed_out": timed_out,
        "returncode": completed.returncode,
        "desktop_returncode": desktop_completed.returncode,
        "desktop_timed_out": desktop_timed_out,
        "stdout": completed.stdout,
        "stderr": "",
        "overall_passed": passed,
    }
    output = root / ".harness" / "verification" / "procedural-construction-editor-runtime-report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"procedural_construction_editor_runtime_report_json={output}")
    print(f"overall_procedural_construction_editor_runtime_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
