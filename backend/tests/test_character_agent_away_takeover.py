from app.services.character_agent_runtime import CharacterAgentRuntime
from app.models.character_agent_runtime import CharacterGoalCommand


def test_away_takeover_allows_only_low_risk_commands() -> None:
    runtime = CharacterAgentRuntime()
    runtime.set_control_mode("char_c", "away_conservative_takeover")

    assert runtime.is_command_allowed_for_mode("away_conservative_takeover", "observe")
    assert runtime.is_command_allowed_for_mode("away_conservative_takeover", "look_at")
    assert runtime.is_command_allowed_for_mode("away_conservative_takeover", "speak")
    assert not runtime.is_command_allowed_for_mode("away_conservative_takeover", "interact")
    assert not runtime.is_command_allowed_for_mode("away_conservative_takeover", "approach")


def test_player_priority_mode_does_not_block_background_low_invasion_execution() -> None:
    runtime = CharacterAgentRuntime()

    assert runtime.is_command_allowed_for_mode("player_priority_assisted", "observe")
    assert runtime.is_command_allowed_for_mode("player_priority_assisted", "speak")


def test_invalid_control_mode_is_rejected() -> None:
    runtime = CharacterAgentRuntime()

    assert not runtime.is_valid_control_mode("human_controlled")
    assert runtime.is_valid_control_mode("player_priority_assisted")


def test_player_priority_assisted_suppresses_autonomous_goal_commands_for_char_c() -> None:
    runtime = CharacterAgentRuntime()
    commands = [
        CharacterGoalCommand(
            actor_id="char_c",
            command_type="observe",
            ttl_ms=1000,
            causation_id="cg:1",
            correlation_id="cg:1",
            producer_ts=1,
        )
    ]

    filtered = runtime.filter_commands_for_actor("char_c", commands)

    assert filtered == []


def test_away_takeover_keeps_only_low_risk_commands_for_char_c() -> None:
    runtime = CharacterAgentRuntime()
    runtime.set_control_mode("char_c", "away_conservative_takeover")
    commands = [
        CharacterGoalCommand(
            actor_id="char_c",
            command_type="observe",
            ttl_ms=1000,
            causation_id="cg:2",
            correlation_id="cg:2",
            producer_ts=2,
        ),
        CharacterGoalCommand(
            actor_id="char_c",
            command_type="interact",
            ttl_ms=1000,
            causation_id="cg:3",
            correlation_id="cg:3",
            producer_ts=3,
        ),
    ]

    filtered = runtime.filter_commands_for_actor("char_c", commands)

    assert [command.command_type for command in filtered] == ["observe"]
