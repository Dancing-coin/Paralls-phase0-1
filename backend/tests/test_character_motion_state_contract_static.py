from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_motion_state_spec_requires_facing_and_camera_fields() -> None:
    control_spec_text = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-12-character-actor-control-and-locomotion-design.md"
    ).read_text(encoding="utf-8")

    assert "facing_yaw" in control_spec_text
    assert "camera_pitch?" in control_spec_text or "camera_pitch" in control_spec_text


def test_motion_state_contract_is_published_in_shared_actor_path() -> None:
    schema_source = (ROOT / "scripts" / "character" / "CharacterActorSchema.gd").read_text(
        encoding="utf-8"
    )
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(encoding="utf-8")
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert '"facing_yaw"' in schema_source
    assert '"camera_pitch"' in schema_source
    assert '"facing_yaw"' in motor_source
    assert '"camera_pitch"' in player_shell_source
