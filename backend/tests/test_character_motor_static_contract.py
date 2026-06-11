from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_motor_script_declares_motor_owner() -> None:
    motor_path = ROOT / "scripts" / "character" / "CharacterMotor.gd"
    assert motor_path.exists(), "CharacterMotor.gd must exist"
    motor_source = motor_path.read_text(encoding="utf-8")

    assert "class_name CharacterMotor" in motor_source
    assert "move_and_slide()" in motor_source


def test_character_base_scene_mounts_character_motor() -> None:
    scene_source = (ROOT / "scenes" / "phase0" / "CharacterBase.tscn").read_text(encoding="utf-8")

    assert 'path="res://scripts/character/CharacterMotor.gd"' in scene_source
    assert '[node name="CharacterMotor" type="Node" parent="."]' in scene_source
