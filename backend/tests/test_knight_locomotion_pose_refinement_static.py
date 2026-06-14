from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_knight_role_skin_refines_head_and_hand_motion_for_player_locomotion() -> None:
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "head_bone" in knight_role_skin_source
    assert "neck_bone" in knight_role_skin_source
    assert "left_hand_bone" in knight_role_skin_source
    assert "right_hand_bone" in knight_role_skin_source
    assert "_apply_head_pose(" in knight_role_skin_source
    assert "_apply_hand_pose(" in knight_role_skin_source
    assert '"head_nod"' in knight_role_skin_source
    assert '"head_yaw"' in knight_role_skin_source
    assert '"hand_swing"' in knight_role_skin_source
    assert '"hand_roll"' in knight_role_skin_source


def test_locomotion_refinement_invokes_head_and_hand_layers() -> None:
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "_apply_head_pose(left_phase, refinement)" in knight_role_skin_source
    assert "_apply_hand_pose(left_hand_bone" in knight_role_skin_source
    assert "_apply_hand_pose(right_hand_bone" in knight_role_skin_source


def test_knight_role_skin_exposes_global_locomotion_amplitude_scaling() -> None:
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "@export var locomotion_amplitude_scale" in knight_role_skin_source
    assert "locomotion_amplitude_scale" in knight_role_skin_source
    assert "_scaled_refinement_value(" in knight_role_skin_source
