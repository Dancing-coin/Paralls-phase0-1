from app.models import character_agent_runtime as runtime_models
from app.services.character_agent_runtime import CharacterAgentRuntime


EXPECTED_STAGE_B_CONTROL_MODES = {
    "agent_full_auto",
    "player_priority_assisted",
    "away_conservative_takeover",
    "scripted_override",
}


def test_stage_b_control_modes_are_frozen() -> None:
    assert set(runtime_models.CHARACTER_AGENT_CONTROL_MODES) == EXPECTED_STAGE_B_CONTROL_MODES


def test_runtime_defaults_char_a_and_char_b_to_agent_full_auto() -> None:
    runtime = CharacterAgentRuntime()

    assert runtime.get_control_mode("char_a") == "agent_full_auto"
    assert runtime.get_control_mode("char_b") == "agent_full_auto"


def test_runtime_defaults_char_c_to_player_priority_assisted() -> None:
    runtime = CharacterAgentRuntime()

    assert runtime.get_control_mode("char_c") == "player_priority_assisted"


def test_runtime_allows_control_mode_switches_for_char_c() -> None:
    runtime = CharacterAgentRuntime()

    runtime.set_control_mode("char_c", "away_conservative_takeover")
    assert runtime.get_control_mode("char_c") == "away_conservative_takeover"

    runtime.set_control_mode("char_c", "scripted_override")
    assert runtime.get_control_mode("char_c") == "scripted_override"
