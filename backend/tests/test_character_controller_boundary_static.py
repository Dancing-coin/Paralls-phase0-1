from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_player_shell_owns_raw_input_forwarding_for_character_actor_bridge() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func _input(event: InputEvent) -> void:" in player_shell_source
    assert "func _unhandled_input(event: InputEvent) -> void:" in player_shell_source
    assert 'var relay := get_node_or_null("Phase0PlayerCommandRelay")' in player_shell_source
    assert 'relay.has_method("handle_shell_action_event")' in player_shell_source
    assert "relay.handle_shell_action_event(event)" in player_shell_source
    assert '["Phase0InputBridge", "Phase0PlayerCommandRelay"]' not in player_shell_source


def test_phase0_player_bridge_is_an_adapter_not_a_parallel_input_reader() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )

    assert "func handle_shell_action_event(event: InputEvent) -> void:" not in bridge_source
    assert "func trigger_dialogue() -> void:" in bridge_source
    assert "func trigger_interaction() -> void:" in bridge_source
    assert "func cycle_gait_mode() -> void:" in bridge_source
    assert "func toggle_crouch_mode() -> void:" in bridge_source
    assert "func trigger_role_action(action_tag: String) -> void:" in bridge_source
    assert "func trigger_combat_action(action_tag: String) -> void:" in bridge_source
    assert "func _trigger_combat_action(action_name: String) -> void:" in bridge_source
    assert "func _trigger_character_c_action(action_name: String) -> void:" in bridge_source

    assert "func _process(_delta: float) -> void:" not in bridge_source
    assert "func _input(event: InputEvent) -> void:" not in bridge_source
    assert "func _unhandled_input(event: InputEvent) -> void:" not in bridge_source
    assert "set_process(true)" not in bridge_source
    assert "set_process_input(true)" not in bridge_source
    assert "set_process_unhandled_input(true)" not in bridge_source
    assert "Input.is_action_pressed(" not in bridge_source
    assert "Input.is_mouse_button_pressed(" not in bridge_source


def test_phase0_player_bridge_delegates_program_forcing_state_to_helper() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    helper_source = (ROOT / "scripts" / "player" / "Phase0ProgramControlState.gd").read_text(
        encoding="utf-8"
    )

    assert "class_name Phase0ProgramControlState" in helper_source
    assert "build_program_intent_frame" in bridge_source
    assert "ProgramControlStateRef" in bridge_source
    assert "program_control_state." in bridge_source
    assert "var forced_move_direction := Vector3.ZERO" not in bridge_source
    assert "var forced_run_state := false" not in bridge_source
    assert "var forced_jump_request := \"\"" not in bridge_source


def test_phase0_player_bridge_delegates_locomotion_mode_state_to_helper() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    helper_source = (ROOT / "scripts" / "player" / "Phase0LocomotionControlState.gd").read_text(
        encoding="utf-8"
    )

    assert "class_name Phase0LocomotionControlState" in helper_source
    assert "LocomotionControlStateRef" in bridge_source
    assert "locomotion_control_state." in bridge_source
    assert "var locomotion_gait_mode := 1" not in bridge_source
    assert "var locomotion_stance_mode := 0" not in bridge_source
    assert "var current_jump_type := \"none\"" not in bridge_source


def test_phase0_player_bridge_delegates_character_shell_sync_to_helper() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    helper_source = (ROOT / "scripts" / "player" / "Phase0CharacterShellSync.gd").read_text(
        encoding="utf-8"
    )

    assert "class_name Phase0CharacterShellSync" in helper_source
    assert "CharacterShellSyncRef" in bridge_source
    assert "character_shell_sync." in bridge_source
    assert "character_c.apply_player_shell_pose(" not in bridge_source
    assert "character_c.begin_player_control_frame(" not in bridge_source
    assert "character_c.clear_player_shell_frame()" not in bridge_source


def test_phase0_character_shell_sync_prefers_actor_facing_aliases_over_wrapper_named_methods() -> None:
    helper_source = (ROOT / "scripts" / "player" / "Phase0CharacterShellSync.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert 'has_method("apply_embodied_pose_sync")' in helper_source
    assert 'has_method("begin_embodied_control_frame")' in helper_source
    assert 'has_method("clear_embodied_control_frame")' in helper_source
    assert 'has_method("apply_player_shell_pose")' not in helper_source
    assert 'has_method("begin_player_control_frame")' not in helper_source
    assert 'has_method("clear_player_shell_frame")' not in helper_source
    assert "func apply_embodied_pose_sync(" in replica_source
    assert "func begin_embodied_control_frame(" in replica_source
    assert "func clear_embodied_control_frame() -> void:" in replica_source
    assert "func apply_player_shell_pose(" not in replica_source
    assert "func begin_player_control_frame(" not in replica_source
    assert "func clear_player_shell_frame() -> void:" not in replica_source


def test_phase0_player_bridge_delegates_view_and_anchor_queries_to_helper() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )

    assert "class_name Phase0ViewAnchorResolver" in helper_source
    assert "ViewAnchorResolverRef" in bridge_source
    assert "view_anchor_resolver." in bridge_source
    assert "player.find_child(\"CameraHolder\"" not in bridge_source
    assert "player.find_child(\"Camera3D\"" not in bridge_source
    assert "func _resolve_player_look_target() -> Vector3:" in bridge_source
    assert "func _resolve_player_forward() -> Vector3:" in bridge_source


def test_view_anchor_resolver_prefers_frozen_wrapper_child_mounts_before_recursive_scene_search() -> None:
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )

    assert 'player.get_node_or_null("CharacterReplica")' in helper_source
    assert 'player.get_node_or_null("CameraHolder")' in helper_source
    assert 'find_child("CharacterReplica", true, false)' not in helper_source
    assert 'find_child("CameraHolder", true, false)' not in helper_source


def test_player_shell_exposes_wrapper_camera_and_anchor_queries_for_player_helpers() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_camera() -> Camera3D:" in player_shell_source
    assert "func get_control_anchor_position() -> Vector3:" in player_shell_source
    assert 'external_motion_driver.has_method("get_control_anchor_position")' in player_shell_source
    assert "return external_motion_driver.get_control_anchor_position()" in player_shell_source
    assert "return global_position" in player_shell_source


def test_camera_occlusion_fader_uses_player_shell_queries_instead_of_bridge_node_lookup() -> None:
    occlusion_source = (ROOT / "scripts" / "player" / "CameraOcclusionFader.gd").read_text(
        encoding="utf-8"
    )

    assert '@onready var player_bridge: Node = player.get_node_or_null("Phase0InputBridge")' not in occlusion_source
    assert 'player.has_method("get_camera")' in occlusion_source
    assert "player.get_camera()" in occlusion_source
    assert 'player.has_method("get_control_anchor_position")' in occlusion_source
    assert "player.get_control_anchor_position()" in occlusion_source


def test_view_anchor_resolver_prefers_player_shell_camera_query_before_recursive_camera_search() -> None:
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )

    assert 'player.has_method("get_camera")' in helper_source
    assert "player.get_camera()" in helper_source


def test_view_anchor_resolver_prefers_player_shell_visual_forward_alias_before_recursive_visual_root_search() -> None:
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_visual_forward() -> Vector3:" in player_shell_source
    assert 'player.has_method("get_visual_forward")' in helper_source
    assert "player.get_visual_forward()" in helper_source


def test_view_anchor_resolver_prefers_actor_facing_anchor_aliases() -> None:
    helper_source = (ROOT / "scripts" / "player" / "Phase0ViewAnchorResolver.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert 'has_method("is_embodied_control_active")' in helper_source
    assert 'has_method("get_embodied_anchor_position")' in helper_source
    assert 'has_method("is_player_shell_active")' not in helper_source
    assert 'has_method("get_role_anchor_position")' not in helper_source
    assert "func is_embodied_control_active() -> bool:" in replica_source
    assert "func get_embodied_anchor_position() -> Vector3:" in replica_source
    assert "func is_player_shell_active() -> bool:" not in replica_source
    assert "func get_role_anchor_position() -> Vector3:" not in replica_source


def test_phase0_player_bridge_prefers_player_shell_aliases_over_dynamic_property_reads() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_motion_state() -> Dictionary:" in player_shell_source
    assert "func get_action_binding(" in player_shell_source
    assert "player.get(\"motion_state\")" not in bridge_source
    assert "player.get(property_name)" not in bridge_source


def test_character_motor_prefers_body_alias_over_dynamic_property_reads() -> None:
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_numeric_setting(" in player_shell_source
    assert "body.get(property_name)" not in motor_source


def test_phase0_player_bridge_prefers_player_shell_state_aliases_over_direct_wrapper_state_reads() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_planar_velocity() -> Vector3:" in player_shell_source
    assert "func is_grounded_state() -> bool:" in player_shell_source
    assert "func get_body_position() -> Vector3:" in player_shell_source
    assert "func get_vertical_velocity() -> float:" in player_shell_source
    assert "player.velocity" not in bridge_source
    assert "player.global_position" not in bridge_source
    assert "player.is_on_floor()" not in bridge_source


def test_phase0_player_bridge_prefers_actor_visibility_alias_over_visual_root_tree_lookup() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "func set_visual_shell_visible(" in replica_source
    assert "get_node_or_null(\"VisualRoot\")" not in bridge_source


def test_phase0_player_bridge_prefers_player_shell_character_alias_over_wrapper_tree_lookup() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func get_character_replica() -> Node:" in player_shell_source
    assert 'player.get_node_or_null("CharacterReplica")' not in bridge_source
