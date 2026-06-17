from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_final_actor_host_choice_is_frozen_in_docs() -> None:
    target_doc = _read("docs/character/character-actor-final-convergence-target.md")
    migration_doc = _read("docs/character/character-actor-migration-status.md")

    assert "current CharacterReplica lineage" in target_doc
    assert "CharacterBase.tscn` remains a player-shell wrapper" in target_doc
    assert "final host choice is frozen as: `CharacterReplica` lineage; `CharacterBase` is wrapper" in migration_doc


def test_current_scene_shape_matches_the_frozen_host_choice() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    player_shell_scene = _read("scenes/phase0/PlayerShell.tscn")
    character_replica_scene = _read("scenes/phase0/CharacterReplica.tscn")
    main_demo_scene = _read("scenes/phase0/MainDemo.tscn")

    assert '[node name="CharacterBase" type="CharacterBody3D"]' in character_base_scene
    assert '[node name="CharacterReplica" parent="." instance=ExtResource("2_character")]' in character_base_scene
    assert '[node name="CharacterMotor" type="Node" parent="."]' not in character_base_scene
    assert '[node name="CharacterMotor" type="Node" parent="."]' in character_replica_scene
    assert '[node name="CharacterReplica" type="Node3D"]' in character_replica_scene
    assert '[node name="PlayerCharacter" parent="." unique_id=' in main_demo_scene
    assert '[node name="CharacterA" parent="." unique_id=' in main_demo_scene
    assert '[node name="CharacterB" parent="." unique_id=' in main_demo_scene
    assert '[node name="CharacterReplica"' not in player_shell_scene


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
    character_replica_scene = _read("scenes/phase0/CharacterReplica.tscn")

    assert '[node name="CameraOcclusionFader" type="Node" parent="."]' in character_base_scene
    assert 'CameraOcclusionFader' not in character_replica_scene


def test_character_base_wrapper_no_longer_mounts_phase0_embodiment_helper() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")

    assert '[node name="Phase0Embodiment" type="Node" parent="."]' not in character_base_scene


def test_character_base_wrapper_no_longer_keeps_separate_visual_root_marker() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    anchor_resolver_source = _read("scripts/player/Phase0ViewAnchorResolver.gd")

    assert '[node name="VisualRoot" type="Node3D" parent="."]' not in character_base_scene
    assert 'find_child("VisualRoot", true, false)' not in bridge_source
    assert 'get_node_or_null("VisualRoot")' in anchor_resolver_source


def test_wrapper_visual_root_consumers_move_to_actor_facing_character_replica_surface() -> None:
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    anchor_resolver_source = _read("scripts/player/Phase0ViewAnchorResolver.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert '_get_character_c()' in bridge_source
    assert 'get_node_or_null("CharacterReplica")' in anchor_resolver_source
    assert 'find_child("CharacterReplica", true, false)' not in anchor_resolver_source
    assert 'has_method("get_embodied_forward_vector")' in anchor_resolver_source
    assert "func get_embodied_forward_vector() -> Vector3:" in replica_source


def test_phase0_player_embodiment_helper_is_removed_from_repo_runtime_surface() -> None:
    character_base_scene = _read("scenes/phase0/CharacterBase.tscn")
    player_scripts = {path.name for path in (ROOT / "scripts" / "player").iterdir()}

    assert '[node name="Phase0Embodiment" type="Node" parent="."]' not in character_base_scene
    assert "Phase0PlayerEmbodiment.gd" not in player_scripts


def test_phase0_player_command_relay_no_longer_owns_wrapper_embodiment_feedback() -> None:
    relay_source = _read("scripts/player/Phase0PlayerCommandRelay.gd")
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert '@onready var embodiment: Node = $"../Phase0Embodiment"' not in relay_source
    assert "trigger_dialogue_feedback" not in relay_source
    assert "trigger_interact_feedback" not in relay_source
    assert "trigger_role_action" in bridge_source
    assert "perform_action(action_name: String)" in replica_source
