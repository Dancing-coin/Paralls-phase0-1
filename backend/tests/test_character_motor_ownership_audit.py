from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_motor_owns_planar_displacement_path() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(encoding="utf-8")
    phase0_bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )

    assert player_shell_source.count("move_and_slide(") == 0
    assert "player.velocity.x =" not in phase0_bridge_source
    assert "player.velocity.z =" not in phase0_bridge_source
    assert motor_source.count("move_and_slide(") >= 1
    assert "body.velocity.x =" in motor_source
    assert "body.velocity.z =" in motor_source
