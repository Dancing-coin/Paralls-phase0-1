from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_character_replica_is_compatibility_host_and_actor_owns_behavior():
    replica = read("scripts/character/CharacterReplica.gd")
    actor = read("scripts/character/CharacterActor.gd")
    assert "extends CharacterActor" in replica
    assert "class_name CharacterActor" in actor
    assert "func begin_embodied_control_frame(" in replica
    assert "func apply_embodied_pose_sync(" in replica
    assert "func clear_embodied_control_frame()" in replica
    assert "func _update_movement(" in actor


def test_external_animation_components_are_present_and_bound():
    controller = read("scripts/character/RoleAnimationController.gd")
    sampler = read("scripts/character/RootMotionSampler.gd")
    skin = read("scripts/street_combat/StreetCharacterSkin.gd")
    assert "extends Node" in controller
    assert "AnimationNodeStateMachine" in controller
    assert "cross_fade_seconds" in controller
    assert "extends Node" in sampler
    assert ":root.x" in sampler
    assert "consume_delta()" in sampler
    assert "RoleAnimationControllerRef" in skin
    assert "RootMotionSamplerRef" in skin


def test_root_motion_is_motor_owned_and_exclusive():
    actor = read("scripts/character/CharacterActor.gd")
    motor = read("scripts/character/CharacterMotor.gd")
    skin = read("scripts/street_combat/StreetCharacterSkin.gd")
    assert 'command["root_motion_exclusive"]' in actor
    assert 'root_motion_exclusive' in motor
    assert "body.move_and_slide()" in motor
    assert "global_position +=" not in skin
    assert "move_and_slide(" not in skin


def test_street_locomotion_loops_and_actions_are_one_shot():
    controller = read("scripts/character/RoleAnimationController.gd")
    assert 'animation.loop_mode = Animation.LOOP_LINEAR' in controller
    assert 'animation.loop_mode = Animation.LOOP_NONE' in controller
    assert '"boxing"' in controller
    assert '"sword_attack"' in controller


def test_streetdemo_baseline_probe_is_bound_to_real_acceptance_scene():
    scene = read("scenes/phase0/StreetCombatDemo.tscn")
    controller = read("scripts/street_combat/StreetCombatDemo.gd")
    assert 'res://scripts/street_combat/StreetCombatDemo.gd' in scene
    assert 'CharacterActionFoundationBaselineProbeRef' in controller
    assert 'UnifiedCharacterActionFoundation.tscn' not in scene
