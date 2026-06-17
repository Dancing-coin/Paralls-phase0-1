from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_player_control_path_uses_normalized_intent_terms() -> None:
    phase0_bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "move_local" in player_shell_source
    assert "desired_facing_yaw" in phase0_bridge_source
    assert "CharacterMotionState" in player_shell_source or "motion_state" in player_shell_source
