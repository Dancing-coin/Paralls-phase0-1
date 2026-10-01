import os
import subprocess
from pathlib import Path


def test_probe_proves_shared_library_and_motor_ownership() -> None:
    godot = os.environ.get(
        "GODOT_BIN",
        r"D:\godot\Godot_v4.6.3-stable_win64_console.exe",
    )
    project_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [
            godot,
            "--headless",
            "--path",
            str(project_root),
            "--script",
            "res://scripts/verification/street_shared_motion_library_probe.gd",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe_output = result.stdout
    assert "shared_library_identity=true" in probe_output
    assert "six_states=true" in probe_output
    assert "animation_tree_active=true" in probe_output
    assert "motor_motion_owner=true" in probe_output
    assert "root_motion_single_consume=true" in probe_output
