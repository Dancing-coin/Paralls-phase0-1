from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_final_actor_host_choice_is_frozen_in_docs() -> None:
    retirement_report = _read("docs/character/character-replica-retirement-report-2026-09-29.md")

    assert "final_state: retired" in retirement_report
    assert "active_scene_instances=0" in retirement_report
    assert "runtime_replica_lookups=0" in retirement_report
    assert "compatibility_call_count=0" in retirement_report


def test_current_scene_shape_matches_the_frozen_host_choice() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    player_shell_scene = _read("scenes/phase0/PlayerShell.tscn")
    character_actor_scene = _read("scenes/phase0/CharacterActor.tscn")
    validation_scene = _read("scenes/integration/Unified3DIntegrationValidation.tscn")

    assert '[node name="CharacterBase" type="CharacterBody3D"]' in character_base_scene
    assert '[node name="CharacterActor" parent="." instance=ExtResource("2_character")]' in character_base_scene
    assert '[node name="CharacterMotor" type="Node" parent="."]' not in character_base_scene
    assert '[node name="CharacterActor" type="CharacterBody3D"]' in character_actor_scene
    assert '[node name="CharacterMotor" type="Node" parent="."]' in character_actor_scene
    assert 'res://scripts/character/CharacterActor.gd' in character_actor_scene
    assert '[node name="PlayerCharacter" parent="." instance=ExtResource("2_player")]' in validation_scene
    assert '[node name="CharacterA" parent="." instance=ExtResource("3_actor")]' in validation_scene
    assert '[node name="CharacterB" parent="." instance=ExtResource("3_actor")]' in validation_scene
    assert 'CharacterReplica' not in player_shell_scene


def test_scene_tree_doc_matches_current_player_wrapper_host_choice() -> None:
    scene_tree_doc = _read("docs/scene tree.md")
    main_demo_block = scene_tree_doc.split("## MainDemo", 1)[1].split("## CharacterReplica", 1)[0]

    assert "PlayerCharacter                 -> CharacterBase.tscn" in scene_tree_doc
    assert "CharacterC" not in scene_tree_doc
    assert "Phase0Embodiment" not in main_demo_block


def test_character_base_wrapper_preserves_player_shell_command_relay_mount() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")

    assert 'path="res://scripts/player/Phase0PlayerCommandRelay.gd"' in character_base_scene
    assert '[node name="Phase0PlayerCommandRelay" type="Node" parent="."]' in character_base_scene


def test_character_base_wrapper_keeps_player_feedback_helpers_outside_character_replica() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    character_actor_scene = _read("scenes/phase0/CharacterActor.tscn")

    assert '[node name="CameraOcclusionFader" type="Node" parent="."]' in character_base_scene
    assert 'CameraOcclusionFader' not in character_actor_scene


def test_character_base_wrapper_no_longer_mounts_phase0_embodiment_helper() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")

    assert '[node name="Phase0Embodiment" type="Node" parent="."]' not in character_base_scene


def test_character_base_wrapper_no_longer_keeps_separate_visual_root_marker() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    anchor_resolver_source = _read("scripts/player/Phase0ViewAnchorResolver.gd")

    assert '[node name="VisualRoot" type="Node3D" parent="."]' not in character_base_scene
    assert 'find_child("VisualRoot", true, false)' not in bridge_source
    assert 'get_node_or_null("VisualRoot")' not in anchor_resolver_source


def test_wrapper_visual_root_consumers_move_to_actor_facing_character_surface() -> None:
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    anchor_resolver_source = _read("scripts/player/Phase0ViewAnchorResolver.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert '_get_character_actor()' in bridge_source
    assert 'get_character_actor()' in anchor_resolver_source
    assert 'get_node_or_null("CharacterReplica")' not in anchor_resolver_source
    assert 'find_child("CharacterReplica", true, false)' not in anchor_resolver_source
    assert 'has_method("get_embodied_forward_vector")' in anchor_resolver_source
    assert "func get_embodied_forward_vector() -> Vector3:" in actor_source


def test_phase0_player_embodiment_helper_is_removed_from_repo_runtime_surface() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    player_scripts = {path.name for path in (ROOT / "scripts" / "player").iterdir()}

    assert '[node name="Phase0Embodiment" type="Node" parent="."]' not in character_base_scene
    assert "Phase0PlayerEmbodiment.gd" not in player_scripts


def test_phase0_player_command_relay_no_longer_owns_wrapper_embodiment_feedback() -> None:
    relay_source = _read("scripts/player/Phase0PlayerCommandRelay.gd")
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    actor_source = _read("scripts/character/CharacterActor.gd")

    assert '@onready var embodiment: Node = $"../Phase0Embodiment"' not in relay_source
    assert "trigger_dialogue_feedback" not in relay_source
    assert "trigger_interact_feedback" not in relay_source
    assert "trigger_role_action" in bridge_source
    assert "perform_action(action_name: String)" in actor_source


def test_active_actor_scenes_have_one_character_body_control_path() -> None:
    player_scene = _read("scenes/phase0/PlayerShell.tscn")
    actor_scene = _read("scenes/phase0/CharacterActor.tscn")

    assert player_scene.count('type="CharacterBody3D"') == 1
    assert actor_scene.count('type="CharacterBody3D"') == 1
    assert actor_scene.count('name="CharacterMotor" type="Node" parent="."') == 1
