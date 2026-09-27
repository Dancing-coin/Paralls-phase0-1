from __future__ import annotations

import os
from pathlib import Path
import subprocess
import pytest

from scripts.verification.common import ensure_backend, stop_backend
from scripts.verification.run_context import run_scope


ROOT = Path(__file__).resolve().parents[3]
GODOT = Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe")


@pytest.fixture(autouse=True)
def harness_scope():
    with run_scope(ROOT):
        yield


def test_three_user_models_bind_real_skeleton_and_animations() -> None:
    env = os.environ.copy()
    env["PARALLS_STREET_PROBE"] = "1"
    result = subprocess.run(
        [str(GODOT), "--headless", "--path", str(ROOT), "--scene", "res://scenes/phase0/StreetCombatDemo.tscn", "--quit-after", "180", "--render-thread", "safe", "--rendering-method", "gl_compatibility"],
        cwd=ROOT, env=env, text=True, capture_output=True, timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "street_combat_probe:skeletons=3" in result.stdout, result.stdout + result.stderr
    assert "street_combat_probe:idle_walk_attack=3" in result.stdout, result.stdout + result.stderr
    assert "street_combat_probe:environment=true:collision=true:navigation=true" in result.stdout, result.stdout + result.stderr
    assert "street_combat_probe:camera_body_facing=true:turn_clip_inactive=true" in result.stdout, result.stdout + result.stderr


def test_player_and_agent_combat_cross_live_websocket() -> None:
    env = os.environ.copy()
    env.update({"PARALLS_STREET_PROBE": "2", "PARALLS_HEAVENLY_GRAPH_PATH": ":memory:", "PARALLS_BACKEND_WS_URL": "ws://127.0.0.1:8000/ws"})
    backend = None
    try:
        _, backend = ensure_backend(ROOT, r"C:\Anaconda3\python.exe", prefer_fresh_backend=True, env=env)
        result = subprocess.run(
            [str(GODOT), "--headless", "--path", str(ROOT), "--scene", "res://scenes/phase0/StreetCombatDemo.tscn", "--quit-after", "2400", "--render-thread", "safe", "--rendering-method", "gl_compatibility"],
            cwd=ROOT, env=env, text=True, capture_output=True, timeout=45,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "street_combat_probe:player_hit=true" in result.stdout, result.stdout + result.stderr
        assert "street_combat_probe:agent_hit=true" in result.stdout, result.stdout + result.stderr
        assert "street_combat_probe:duplicate_stale_recovery=true" in result.stdout, result.stdout + result.stderr
        assert "street_combat_probe:stale_rejected=true" in result.stdout, result.stdout + result.stderr
        assert "street_combat_probe:recovery_committed=true" in result.stdout, result.stdout + result.stderr
        assert "street_combat_probe:imported_attack_playback=true" in result.stdout, result.stdout + result.stderr
        assert "street_combat_probe:hud_actions_and_stamina=true" in result.stdout, result.stdout + result.stderr
    finally:
        stop_backend(backend)
