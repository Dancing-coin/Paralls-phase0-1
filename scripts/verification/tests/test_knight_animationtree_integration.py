from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_knight_role_skin_scene_declares_animation_tree_node() -> None:
    scene_text = (ROOT / "scenes" / "phase0" / "KnightRoleSkin.tscn").read_text(encoding="utf-8")

    assert 'node name="AnimationTree" type="AnimationTree" parent="."' in scene_text
    assert "tree_root = SubResource(" in scene_text
    assert 'anim_player = NodePath("KnightScene/AnimationPlayer")' in scene_text


def test_knight_role_skin_script_uses_animation_tree_playback() -> None:
    script_text = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(encoding="utf-8")

    assert "AnimationNodeStateMachinePlayback" in script_text
    assert "animation_state_playback.travel" in script_text
