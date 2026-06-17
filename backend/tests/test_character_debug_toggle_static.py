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

    assert "attention_target_environment:" not in replica_source
    assert "character_actor_status:" not in replica_source
    assert "runtime_state_applied:" not in replica_source
    assert "role_action_overlay:sword_swing" in role_skin_source
    assert "role_action_overlay:shield_block" in role_skin_source
