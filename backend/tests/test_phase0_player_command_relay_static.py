from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase0_player_command_relay_owns_demo_shell_commands() -> None:
    relay_source = (ROOT / "scripts" / "player" / "Phase0PlayerCommandRelay.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    shell_scene = (ROOT / "scenes" / "phase0" / "PlayerShell.tscn").read_text(
        encoding="utf-8"
    )

    assert "func handle_shell_action_event(event: InputEvent) -> void:" in relay_source
    assert "dialogue_action" in relay_source
    assert "interact_action" in relay_source
    assert "gait_cycle_action" in relay_source
    assert "crouch_toggle_action" in relay_source
    assert "guard_pose_action" in relay_source
    assert "sword_swing_action" in relay_source
    assert "shield_block_action" in relay_source
    assert "func trigger_dialogue() -> void:" in bridge_source
    assert "func trigger_interaction() -> void:" in bridge_source
    assert "func cycle_gait_mode() -> void:" in bridge_source
    assert "func toggle_crouch_mode() -> void:" in bridge_source
    assert "func trigger_role_action(action_tag: String) -> void:" in bridge_source
    assert "func trigger_combat_action(action_tag: String) -> void:" in bridge_source
    assert "func handle_shell_action_event(event: InputEvent) -> void:" not in bridge_source
    assert "@export var dialogue_action" not in bridge_source
    assert "@export var interact_action" not in bridge_source
    assert "@export var guard_pose_action" not in bridge_source
    assert "@export var sword_swing_action" not in bridge_source
    assert "@export var shield_block_action" not in bridge_source
    assert '[node name="Phase0PlayerCommandRelay"' in shell_scene
