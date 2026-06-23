from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_main_demo_enables_debug_logging_explicitly_for_autotest_and_harness() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert 'OS.get_environment("PHASE0_DEBUG_LOGGING") == "1"' in controller_source
    assert "bus.set_debug_logging_enabled(" in controller_source
    assert "autotest_enabled or focus_autotest_enabled" in controller_source


def test_backend_default_runtime_path_no_longer_hides_observatory_delivery_behind_private_toggle() -> None:
    main_source = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")

    assert "PHASE0_OBSERVATORY_STREAM" not in main_source
    assert "OBSERVATORY_STREAM_ENABLED" not in main_source
    assert "messages.extend(_observatory_messages_from_outbound(messages))" in main_source


def test_main_demo_does_not_keep_unused_debug_message_cache_state() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "var last_debug_message := \"\"" not in controller_source
    assert "last_debug_message = message" not in controller_source


def test_main_demo_does_not_keep_unused_autotest_capture_delay_export() -> None:
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )

    assert "@export var autotest_capture_delay := 0.8" not in controller_source


def test_actor_runtime_scripts_trim_unused_default_migration_diagnostics() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(
        encoding="utf-8"
    )
    bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    debug_doc = (ROOT / "docs" / "character" / "character-debug-and-verification.md").read_text(
        encoding="utf-8"
    )
    control_chain_doc = (ROOT / "docs" / "character" / "character-control-chain.md").read_text(
        encoding="utf-8"
    )

    assert "attention_target_environment:" not in replica_source
    assert "character_actor_status:" not in replica_source
    assert "runtime_state_applied:" not in replica_source
    assert "player_shell_mouse_button:button=%s pressed=%s device=%s" not in player_shell_source
    assert "mouse_button_state:left=%s right=%s" not in player_shell_source
    assert "phase0_input_bridge_ready:combat_mouse_v3" not in bridge_source
    assert "combat_mouse_event:button=%s pressed=%s device=%s" not in bridge_source
    assert '"player_combat_action:%s" % action_name' not in bridge_source
    assert "player_shell_mouse_button:*" not in debug_doc
    assert "mouse_button_state:*" not in debug_doc
    assert "combat_mouse_event:*" not in debug_doc
    assert "player_combat_action:*" not in debug_doc
    assert "player_shell_mouse_button:*" not in control_chain_doc
    assert "combat_mouse_event:*" not in control_chain_doc
    assert "player_combat_action:*" not in control_chain_doc
    assert "role_action_overlay:sword_swing" in role_skin_source
    assert "role_action_overlay:shield_block" in role_skin_source
