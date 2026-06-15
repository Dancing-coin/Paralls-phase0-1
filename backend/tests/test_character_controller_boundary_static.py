from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_player_shell_owns_raw_input_forwarding_for_character_actor_bridge() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )

    assert "func _input(event: InputEvent) -> void:" in player_shell_source
    assert "func _unhandled_input(event: InputEvent) -> void:" in player_shell_source
    assert 'has_method("handle_shell_action_event")' in player_shell_source
    assert '["Phase0InputBridge", "Phase0PlayerCommandRelay"]' in player_shell_source
    assert "target.handle_shell_action_event(event)" in player_shell_source


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
