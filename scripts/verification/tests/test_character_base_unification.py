from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_character_base_scene_exists_with_body_and_camera_shell() -> None:
    scene_text = (ROOT / "scenes" / "phase0" / "CharacterBase.tscn").read_text(encoding="utf-8")

    assert 'type="CharacterBody3D"' in scene_text
    assert 'node name="CameraHolder" type="Node3D" parent="."' in scene_text
    assert 'node name="CharacterReplica"' in scene_text


def test_main_demo_uses_single_player_character_instance() -> None:
    scene_text = (ROOT / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")

    assert 'path="res://scenes/phase0/CharacterBase.tscn"' in scene_text
    assert '[node name="PlayerCharacter"' in scene_text
    assert '[node name="CharacterC"' not in scene_text


def test_phase0_player_bridge_no_longer_looks_up_characterc_node() -> None:
    script_text = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(encoding="utf-8")

    assert 'get_node_or_null("CharacterC")' not in script_text
