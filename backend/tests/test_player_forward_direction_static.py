from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_player_bridge_uses_motor_forward_convention_for_move_and_look() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )

    assert "func _forward_from_yaw(yaw: float) -> Vector3:" in bridge_source
    assert "return -Vector3.FORWARD.rotated(Vector3.UP, yaw).normalized()" in bridge_source
    assert "return player.global_position + _forward_from_yaw(desired_facing_yaw)" in bridge_source
    assert "var forward := _forward_from_yaw(facing_yaw)" in bridge_source


def test_player_shell_normalizes_w_as_positive_local_forward() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "var raw_move_local := Input.get_vector(" in player_shell_source
    assert "move_forward_action" in player_shell_source
    assert "move_backward_action" in player_shell_source
    assert "return Vector2(raw_move_local.x, -raw_move_local.y)" in player_shell_source
