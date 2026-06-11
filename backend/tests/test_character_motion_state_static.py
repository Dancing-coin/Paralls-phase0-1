from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_motion_state_drives_presentation_path() -> None:
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(encoding="utf-8")
    character_replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "move_local_actual" in motor_source or "velocity_world" in motor_source
    assert "motion_state" in character_replica_source
    assert "speed" in knight_role_skin_source
    assert "move_x" in knight_role_skin_source or "move_y" in knight_role_skin_source
