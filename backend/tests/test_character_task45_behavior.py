from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
GODOT_CANDIDATES = (
    Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe"),
    Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe"),
)


def _godot() -> Path | None:
    configured = os.environ.get("GODOT_EXE")
    candidates = (Path(configured),) if configured else GODOT_CANDIDATES
    return next((path for path in candidates if path.exists()), None)


@pytest.mark.skipif(_godot() is None, reason="Godot executable is unavailable")
def test_task45_headless_probe_observes_shared_path_and_contact_contract() -> None:
    executable = _godot()
    assert executable is not None
    result = subprocess.run(
        [str(executable), "--headless", "--path", str(ROOT), "--script", "res://scripts/verification/CharacterTask45Probe.gd"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["shared_command"] is True
    assert payload["policy_contract"] is True
    assert payload["evidence_contract"] is True
    assert payload["recovery_contract"] is True
    assert payload["stale_correction_contract"] is True
    assert payload["surface_constraints"] is True


def test_task45_static_guard_removes_replica_motion_and_facing_writers() -> None:
    replica = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")
    player = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(encoding="utf-8")
    process_body = replica.split("func _process(", 1)[1].split("func _physics_process(", 1)[0]
    assert "_update_movement" not in process_body
    assert "_update_rotation" not in process_body
    assert "rotation.y -=" not in player
    assert "MotionContributionComposer" in replica
    assert "CharacterControllerPort" in replica
