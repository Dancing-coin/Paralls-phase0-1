from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import repo_root


def test_main_demo_uses_local_phase0_player_scene() -> None:
    root = repo_root()
    main_scene = (root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    player_scene = root / "scenes" / "phase0" / "Phase0Player.tscn"

    assert player_scene.exists()
    assert 'path="res://scenes/phase0/Phase0Player.tscn"' in main_scene
    assert "JehenoThirdPersonController/PlayerCharacter/player_character_scene.tscn" not in main_scene


def test_main_demo_has_no_external_import_cache_dependencies() -> None:
    root = repo_root()
    main_scene = (root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    player_bridge = (root / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(encoding="utf-8")

    assert "assets/environment/throne_room_existing" not in main_scene
    assert ".godot/imported" not in main_scene
    assert "ThroneHallWalkPreview.tscn" not in main_scene
    assert "PlayerCharacter" not in player_bridge


def test_phase0_player_scene_exposes_required_runtime_nodes() -> None:
    root = repo_root()
    player_scene = (root / "scenes" / "phase0" / "Phase0Player.tscn").read_text(encoding="utf-8")

    assert '[node name="Phase0Player" type="CharacterBody3D"]' in player_scene
    assert '[node name="VisualRoot" type="Node3D" parent="."]' in player_scene
    assert '[node name="CameraHolder" type="Node3D" parent="."]' in player_scene
    assert '[node name="SpringArm3D" type="SpringArm3D" parent="CameraHolder"]' in player_scene
    assert '[node name="Camera3D" type="Camera3D" parent="CameraHolder/SpringArm3D"]' in player_scene


def test_character_replica_uses_greybox_without_external_plush_import_cache() -> None:
    root = repo_root()
    replica_scene = (root / "scenes" / "phase0" / "CharacterReplica.tscn").read_text(encoding="utf-8")
    replica_script = (root / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")

    assert "JehenoThirdPersonController/PlayerCharacter/GodotPlush" not in replica_scene
    assert "GodotPlushSkin" not in replica_scene
    assert 'get_node_or_null("VisualRoot/AssetMount/RotationOffset/ScaleOffset/ImportedModel/RoleAssetRoot/GodotPlushSkin")' in replica_script


def test_autotest_orientation_does_not_recompute_forced_focus() -> None:
    root = repo_root()
    controller = (root / "scripts" / "phase0" / "MainDemoController.gd").read_text(encoding="utf-8")

    assert "func _orient_player_toward(target_position: Vector3) -> void:" in controller
    assert "if not focus_override_active:\n\t\t_update_focus_target()" in controller


def test_main_demo_wires_siming_visual_observability_presenter() -> None:
    root = repo_root()
    scene_text = (root / "scenes" / "phase0" / "MainDemo.tscn").read_text(encoding="utf-8")
    script_text = (root / "scripts" / "phase0" / "SimingVisualObservabilityPresenter.gd").read_text(encoding="utf-8")

    assert "SimingVisualObservabilityPresenter" in scene_text
    assert "siming_visual_observability_requested.connect" in script_text
    assert "siming_visual_observability_applied" in script_text
    assert "siming_visual_observability_rejected" in script_text
