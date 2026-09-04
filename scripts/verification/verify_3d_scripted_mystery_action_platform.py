from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json


def main() -> int:
    root = repo_root()
    artifact = verification_dir(root) / "3d-scripted-mystery-action-platform-report.json"
    log = verification_dir(root) / "3d-scripted-mystery-action-platform-pytest.log"
    python_exe = resolve_python_exe(None)
    result = run_command(
        [python_exe, "-m", "pytest", "-q", "backend/tests/test_scripted_mystery_projection.py", "backend/tests/test_3d_scripted_mystery_action_replay.py", "backend/tests/test_action_window_godot_contract_static.py"],
        root,
        log,
    )
    scene = root / "scenes" / "phase0" / "ScriptedMysteryActionProbe.tscn"
    script = root / "scripts" / "verification" / "ScriptedMysteryActionProbe.gd"
    report = {
        "overall_passed": result.returncode == 0 and scene.exists() and script.exists(),
        "godot_runtime_verified": False,
        "static_scene_present": scene.exists(),
        "procedural_script_present": script.exists(),
        "pytest_log": str(log),
        "note": "Godot desktop/headless probe was not available in this environment; backend/static evidence is recorded without claiming runtime verification.",
    }
    write_json(artifact, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
