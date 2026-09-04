from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()
    root = repo_root()
    artifact = verification_dir(root) / "3d-scripted-mystery-action-platform-report.json"
    log = verification_dir(root) / "3d-scripted-mystery-action-platform-pytest.log"
    python_exe = resolve_python_exe(args.python_exe)
    result = run_command(
        [python_exe, "-m", "pytest", "-q", "backend/tests/test_scripted_mystery_projection.py", "backend/tests/test_3d_scripted_mystery_action_replay.py", "backend/tests/test_action_window_godot_contract_static.py"],
        root,
        log,
    )
    scene = root / "scenes" / "phase0" / "ScriptedMysteryActionProbe.tscn"
    script = root / "scripts" / "verification" / "ScriptedMysteryActionProbe.gd"
    godot_log = verification_dir(root) / "3d-scripted-mystery-action-platform-godot.log"
    godot_artifact = verification_dir(root) / "scripted-mystery-action-godot-runtime.json"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command(
            [args.godot_exe, "--headless", "--path", str(root), "--scene", "res://scenes/phase0/ScriptedMysteryActionProbe.tscn", "--quit-after", "300", "--render-thread", "safe"],
            root,
            godot_log,
        )
        godot_ok = godot_result.returncode == 0 and "scripted_mystery_action_probe:verified=true" in godot_log.read_text(encoding="utf-8", errors="replace") and godot_artifact.exists()
    report = {
        "overall_passed": result.returncode == 0 and scene.exists() and script.exists() and (godot_ok if args.godot_exe else True),
        "godot_runtime_verified": godot_ok,
        "static_scene_present": scene.exists(),
        "procedural_script_present": script.exists(),
        "pytest_log": str(log),
        "godot_log": str(godot_log),
        "godot_artifact": str(godot_artifact),
        "note": "Godot runtime is verified when --godot-exe is supplied; otherwise the report remains static/backend-only.",
    }
    write_json(artifact, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
