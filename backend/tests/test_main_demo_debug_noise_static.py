from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_main_demo_disables_character_a_and_b_patrol_for_debuggable_player_input() -> None:
    scene_source = (ROOT / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")

    assert '[node name="CharacterA" parent="."' in scene_source
    assert '[node name="CharacterB" parent="."' in scene_source
    assert "CharacterA" in scene_source and "patrol_enabled = false" in scene_source
    assert "CharacterB" in scene_source and "patrol_enabled = false" in scene_source
