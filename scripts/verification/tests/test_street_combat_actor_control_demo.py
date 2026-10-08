from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCENE = ROOT / "scenes" / "phase0" / "StreetCombatActorControlDemo.tscn"
CONTROLLER = ROOT / "scripts" / "street_combat" / "StreetCombatActorControlDemo.gd"
INPUT = ROOT / "scripts" / "character" / "control" / "CharacterPlayerInputSource.gd"
CAMERA = ROOT / "scripts" / "character" / "control" / "CharacterCameraController.gd"
FOUNDATION = ROOT / "scripts" / "character" / "control" / "CharacterControlFoundation.gd"
ACTOR_SCENE = ROOT / "scenes" / "phase0" / "CharacterActor.tscn"
REGISTRY = ROOT / "scripts" / "character" / "CharacterEmbodimentAssetRegistry.gd"
PRESENTATION = ROOT / "scripts" / "character" / "CharacterPresentationAdapter.gd"


def test_control_demo_is_a_copy_with_explicit_control_components() -> None:
    scene = SCENE.read_text(encoding="utf-8")
    assert 'name="StreetCombatActorControlDemo"' in scene
    assert 'path="res://scripts/street_combat/StreetCombatActorControlDemo.gd"' in scene
    assert 'path="res://scripts/character/control/CharacterPlayerInputSource.gd"' in scene
    assert 'path="res://scripts/character/control/CharacterCameraController.gd"' in scene
    assert 'path="res://scripts/character/control/CharacterControlFoundation.gd"' in scene
    assert 'name="ControlInput"' in scene
    assert 'name="ControlCamera"' in scene
    assert 'name="CharacterControlFoundation"' in scene
    assert scene.count('instance=ExtResource("actor")') == 4
    assert scene.count('motion_library_id = "motionlib:humanoid.v1.core@1"') == 3
    assert 'path="res://assets/active/crusader_knight/crusader_knight.glb"' in scene
    assert 'metadata/package_id = "crusader_knight"' in scene
    assert 'name="PackagePresentation"' in scene


def test_control_demo_keeps_character_actor_as_motion_owner() -> None:
    controller = CONTROLLER.read_text(encoding="utf-8")
    foundation = FOUNDATION.read_text(encoding="utf-8")
    assert "apply_player_frame" in controller
    assert "begin_embodied_control_frame" in foundation
    assert "active_actor.velocity" not in controller
    assert "active_actor.move_and_slide" not in controller
    assert "_request_attack" in controller


def test_control_components_have_single_responsibilities() -> None:
    input_script = INPUT.read_text(encoding="utf-8")
    camera_script = CAMERA.read_text(encoding="utf-8")
    assert "action_requested" in input_script
    assert "actor_switch_requested" in input_script
    assert "jump_requested" in input_script
    assert "Input.get_vector" in input_script
    assert "camera.global_position" in camera_script
    assert "camera.look_at" in camera_script
    assert "Input.get_vector" not in camera_script
    foundation = FOUNDATION.read_text(encoding="utf-8")
    assert "class_name CharacterControlFoundation" in foundation
    assert "class_name CharacterPlayerInputSource" in input_script
    assert "class_name CharacterCameraController" in camera_script
    assert "actor_paths" in foundation
    assert "active_actor_changed" in foundation
    assert "CharacterActor.DriverMode.PLAYER" in foundation


def test_foundation_and_presentation_are_scene_and_model_neutral() -> None:
    foundation = FOUNDATION.read_text(encoding="utf-8")
    actor_scene = ACTOR_SCENE.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8")
    presentation = PRESENTATION.read_text(encoding="utf-8")
    assert 'actor_group := "character_control_actor"' in foundation
    assert 'groups=["character_control_actor"]' in actor_scene
    assert "register_project_package" in registry
    assert "register_project_motion_library" in registry
    assert "CharacterPresentationAdapter" in presentation
    assert "KnightScene" not in foundation
    assert "StreetCombat" not in foundation


def test_knight_is_registered_through_generic_package_adapter() -> None:
    scene = SCENE.read_text(encoding="utf-8")
    package_adapter = ROOT / "scripts" / "character" / "CharacterPackagePresentationAdapter.gd"
    assert 'path="res://scripts/character/CharacterPackagePresentationAdapter.gd"' in scene
    assert 'path="res://assets/active/crusader_knight/crusader_knight.glb"' in scene
    assert 'package_id = "crusader_knight"' in scene
    assert 'manifest_path = "res://assets/active/crusader_knight/manifest.json"' in scene
    assert 'name="KnightRoleSkin"' not in scene
    assert package_adapter.exists()
