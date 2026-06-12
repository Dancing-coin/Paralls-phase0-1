from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_actor_schema_is_shared_across_motor_shell_and_presentation() -> None:
    schema_source = (ROOT / "scripts" / "character" / "CharacterActorSchema.gd").read_text(
        encoding="utf-8"
    )
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "class_name CharacterActorSchema" in schema_source
    assert "MOTION_STATE_KEYS" in schema_source
    assert "PRESENTATION_INPUT_KEYS" in schema_source
    assert "CharacterActorSchema" in motor_source
    assert "CharacterActorSchema" in player_shell_source
    assert "CharacterActorSchema" in replica_source
    assert "CharacterActorSchema" in knight_role_skin_source


def test_motion_state_and_presentation_input_are_normalized_through_shared_helpers() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    knight_role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "_normalize_motion_state" in replica_source
    assert "_normalize_presentation_input" in replica_source
    assert "_normalize_presentation_input" in knight_role_skin_source
