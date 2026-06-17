from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_locked_control_rules_and_locomotion_axes_are_explicit() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "look_pitch" in player_shell_source
    assert "strafe" in knight_role_skin_source.lower() or "move_x" in knight_role_skin_source
    assert "backpedal" in knight_role_skin_source.lower() or "move_y" in knight_role_skin_source
