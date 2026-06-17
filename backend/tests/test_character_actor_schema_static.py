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
    assert "CharacterActorSchema" in motor_source
    assert "CharacterActorSchema" in player_shell_source
    assert "CharacterActorSchema" in replica_source
    assert "CharacterActorSchema" not in knight_role_skin_source


def test_motion_state_and_presentation_input_are_normalized_through_shared_helpers() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    runtime_state_source = (ROOT / "scripts" / "character" / "CharacterRuntimeState.gd").read_text(
        encoding="utf-8"
    )

    assert "_normalize_motion_state" in replica_source
    assert "_normalize_presentation_input" not in replica_source
    assert 'const CharacterActorSchemaRef = preload("res://scripts/character/CharacterActorSchema.gd")' in runtime_state_source
    assert "CharacterPresentationInputRef.from_player_runtime_state(" in runtime_state_source
    assert "CharacterPresentationInputRef.from_agent_execution_plan(" in runtime_state_source
    assert "CharacterActorSchemaRef.get_velocity_world(" in runtime_state_source
    assert "CharacterActorSchemaRef.is_grounded(" in runtime_state_source
    assert "CharacterActorSchemaRef.get_move_local_actual(" in runtime_state_source
    assert "CharacterActorSchemaRef.get_gait_actual(" in runtime_state_source


def test_character_actor_schema_no_longer_defines_flat_presentation_contract_keys() -> None:
    schema_source = (ROOT / "scripts" / "character" / "CharacterActorSchema.gd").read_text(
        encoding="utf-8"
    )

    assert "PRESENTATION_INPUT_KEYS" not in schema_source
    assert "func normalize_presentation_input" not in schema_source


def test_character_actor_schema_exposes_motion_state_field_helpers() -> None:
    schema_source = (ROOT / "scripts" / "character" / "CharacterActorSchema.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_velocity_world(" in schema_source
    assert "func is_grounded(" in schema_source
    assert "func get_move_local_actual(" in schema_source
    assert "func get_gait_actual(" in schema_source
