from __future__ import annotations

from pathlib import Path

from app.models import character_agent_runtime as runtime_models
from app.services.character_agent_runtime import CharacterAgentRuntime


ROOT = Path(__file__).resolve().parents[2]

EXPECTED_AUTONOMY_MODES = {
    "human_controlled",
    "agent_controlled",
    "idle_autonomous",
    "away_conservative_takeover",
    "scripted_test",
}

EXPECTED_SHARED_COMMANDS = {
    "look_at",
    "go_to",
    "approach",
    "observe",
    "interact",
    "speak",
}


def test_autonomy_modes_and_shared_command_surface_are_frozen() -> None:
    assert set(runtime_models.CHARACTER_ACTOR_AUTONOMY_MODES) == EXPECTED_AUTONOMY_MODES
    assert set(runtime_models.SHARED_CHARACTER_COMMANDS) == EXPECTED_SHARED_COMMANDS


def test_away_conservative_takeover_has_low_risk_command_permissions() -> None:
    runtime = CharacterAgentRuntime()

    assert runtime.is_command_allowed_for_mode("away_conservative_takeover", "observe")
    assert runtime.is_command_allowed_for_mode("away_conservative_takeover", "look_at")
    assert runtime.is_command_allowed_for_mode("away_conservative_takeover", "speak")
    assert not runtime.is_command_allowed_for_mode("away_conservative_takeover", "interact")


def test_speak_is_embodied_not_generated_by_character_actor() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )

    assert "func _apply_embodied_speak(payload: Dictionary) -> void:" in replica_source
    assert "CharacterAgent / DialogueService owns text" in replica_source
    assert "SpatialVoiceController" in replica_source
    assert "dialogue_text" in replica_source
