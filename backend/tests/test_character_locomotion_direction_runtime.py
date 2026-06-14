from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_control_spec_preserves_full_direction_set_and_transitional_compromise() -> None:
    control_spec_text = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-12-character-actor-control-and-locomotion-design.md"
    ).read_text(encoding="utf-8")

    for direction_marker in {
        "forward",
        "backpedal",
        "strafe left",
        "strafe right",
        "forward-left",
        "forward-right",
        "backward-left",
        "backward-right",
    }:
        assert direction_marker in control_spec_text

    assert "forward locomotion with root-motion projection" in control_spec_text
    assert "not the final control model" in control_spec_text


def test_knight_role_skin_exposes_move_axes_for_directional_coverage() -> None:
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "move_x" in knight_role_skin_source
    assert "move_y" in knight_role_skin_source
    assert "strafe_shift" in knight_role_skin_source
    assert "backpedal_pitch" in knight_role_skin_source
