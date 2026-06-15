from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_player_combat_input_actions_are_declared() -> None:
    project_source = (ROOT / "project.godot").read_text(encoding="utf-8")

    assert "phase0_sword_swing" in project_source
    assert "button_index\":1" in project_source or "button_index\": 1" in project_source
    assert "phase0_shield_block" in project_source
    assert "button_index\":2" in project_source or "button_index\": 2" in project_source
    sword_action = re.search(r"phase0_sword_swing=\{.*?\n\}", project_source, re.DOTALL)
    shield_action = re.search(r"phase0_shield_block=\{.*?\n\}", project_source, re.DOTALL)
    assert sword_action is not None
    assert shield_action is not None
    assert '"device":-1' in sword_action.group(0)
    assert '"device":-1' in shield_action.group(0)


def test_player_bridge_dispatches_mouse_combat_actions_to_character_c() -> None:
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    relay_source = (ROOT / "scripts" / "player" / "Phase0PlayerCommandRelay.gd").read_text(
        encoding="utf-8"
    )

    assert "func handle_shell_action_event(event: InputEvent) -> void:" in relay_source
    assert "sword_swing_pressed" in relay_source
    assert "shield_block_pressed" in relay_source
    assert "event.is_action_pressed(sword_swing_action)" in relay_source
    assert "event.is_action_pressed(shield_block_action)" in relay_source
    assert "func trigger_combat_action(action_tag: String) -> void:" in bridge_source
    assert "MOUSE_BUTTON_LEFT" in bridge_source
    assert "MOUSE_BUTTON_RIGHT" in bridge_source
    assert "func handle_mouse_combat_event(event: InputEventMouseButton) -> void:" in bridge_source
    assert "sword_swing_action" in relay_source
    assert "shield_block_action" in relay_source
    assert '_trigger_combat_action("sword_swing")' in bridge_source
    assert '_trigger_combat_action("shield_block")' in bridge_source
    assert "_trigger_character_c_action(action_name)" in bridge_source
    assert '"player_combat_action:%s" % action_name' in bridge_source
    assert "phase0_input_bridge_ready:combat_mouse_v3" in bridge_source
    assert "combat_mouse_event:button=%s pressed=%s device=%s" in bridge_source


def test_player_shell_instantiates_phase0_input_bridge() -> None:
    player_shell_source = (ROOT / "scenes" / "phase0" / "PlayerShell.tscn").read_text(
        encoding="utf-8"
    )

    assert '[ext_resource type="Script" path="res://scripts/player/Phase0PlayerBridge.gd"' in player_shell_source
    assert '[node name="Phase0InputBridge" type="Node" parent="."]' in player_shell_source
    assert 'script = ExtResource("3_bridge")' in player_shell_source


def test_player_shell_forwards_raw_mouse_buttons_to_combat_bridge() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func _input(event: InputEvent) -> void:" in player_shell_source
    assert "func _forward_combat_mouse_event(event: InputEvent) -> void:" in player_shell_source
    assert "event is InputEventMouseButton" in player_shell_source
    assert 'has_method("handle_mouse_combat_event")' in player_shell_source
    assert "external_motion_driver.handle_mouse_combat_event(event as InputEventMouseButton)" in player_shell_source
    assert "player_shell_mouse_button:button=%s pressed=%s device=%s" in player_shell_source
    assert "mouse_button_state:left=%s right=%s" in player_shell_source


def test_character_replica_maps_combat_actions_to_role_states() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert '"sword_swing"' in replica_source
    assert '"shield_block"' in replica_source
    assert 'return "sword_swing"' in replica_source
    assert 'return "shield_block"' in replica_source
    assert "combat_feedback_timer" in replica_source
    assert "_show_combat_feedback(" in replica_source
    assert '"SWING"' in replica_source
    assert '"BLOCK"' in replica_source


def test_knight_role_skin_has_sword_and_shield_pose_overlays() -> None:
    knight_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert '"sword_swing"' in knight_source
    assert '"shield_block"' in knight_source
    assert "_sync_combat_modifier()" in knight_source
    assert "func _build_combat_modifier_input() -> Dictionary:" in knight_source
    assert 'combat_modifier.call("set_modifier_input"' in knight_source
    assert "role_action_overlay:sword_swing" in knight_source
    assert "role_action_overlay:shield_block" in knight_source
    assert "if sword_swing_timer > 0.0 or shield_block_timer > 0.0:" in knight_source
    assert "return 0.0" in knight_source
    assert "sword_swing_timer = 0.78" in knight_source
    assert "shield_block_timer = 0.92" in knight_source


def test_knight_role_skin_scene_wires_combat_modifier() -> None:
    scene_source = (ROOT / "scenes" / "phase0" / "KnightRoleSkin.tscn").read_text(encoding="utf-8")

    assert 'res://scripts/character/KnightCombatModifier.gd' in scene_source
    assert '[node name="KnightCombatModifier"' in scene_source


def test_knight_combat_modifier_contains_post_animation_overlay_logic() -> None:
    modifier_source = (ROOT / "scripts" / "character" / "KnightCombatModifier.gd").read_text(
        encoding="utf-8"
    )

    assert "extends SkeletonModifier3D" in modifier_source
    assert "func _process_modification() -> void:" in modifier_source
    assert "func set_sword_overlay(" in modifier_source
    assert "func set_shield_overlay(" in modifier_source
    assert "sword_in_hand" in modifier_source
    assert "shield_in_hand" in modifier_source
    assert "-1.32 * slash_phase" in modifier_source
    assert "1.28 * brace_phase" in modifier_source


def test_debug_overlay_promotes_combat_trace_lines() -> None:
    overlay_source = (ROOT / "scripts" / "ui" / "DebugOverlay.gd").read_text(
        encoding="utf-8"
    )

    assert 'message.begins_with("global_input:")' in overlay_source
    assert 'message.begins_with("global_unhandled_input:")' in overlay_source
    assert 'message.begins_with("player_shell_mouse_button:")' in overlay_source
    assert 'message.begins_with("mouse_button_state:")' in overlay_source
    assert 'message.begins_with("combat_mouse_event:")' in overlay_source
    assert 'message.begins_with("player_combat_action:")' in overlay_source
    assert 'message.begins_with("role_action_overlay:")' in overlay_source
    assert 'message.begins_with("phase0_input_bridge_ready:")' in overlay_source
    assert 'sections.append("Combat Trace")' in overlay_source
