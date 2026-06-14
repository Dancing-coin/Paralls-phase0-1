from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_character_control_mode_contract_is_frozen() -> None:
    source = _read("scripts/character/CharacterControlMode.gd")

    assert "class_name CharacterControlMode" in source
    assert 'const HUMAN_CONTROLLED := "human_controlled"' in source
    assert 'const AGENT_CONTROLLED := "agent_controlled"' in source
    assert 'const PROGRAM_CONTROLLED := "program_controlled"' in source
    assert "ALLOWED_TRANSITIONS" in source


def test_character_locomotion_execution_mode_contract_is_frozen() -> None:
    source = _read("scripts/character/CharacterLocomotionExecutionMode.gd")

    assert "class_name CharacterLocomotionExecutionMode" in source
    assert 'const PHYSICS := "physics"' in source
    assert 'const ROOT_MOTION := "root_motion"' in source
    assert 'const HYBRID := "hybrid"' in source


def test_character_presentation_input_contract_exists() -> None:
    source = _read("scripts/character/CharacterPresentationInput.gd")

    assert "class_name CharacterPresentationInput" in source
    assert "PRESENTATION_INPUT_KEYS" in source
    assert '"motion_state"' in source
    assert '"action_state"' in source
    assert '"equipment_state"' in source
    assert '"speech_state"' in source


def test_shared_character_actor_scripts_reference_frozen_vocabulary() -> None:
    player_shell_source = _read("scripts/player/PlayerShell.gd")
    bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "CharacterControlMode" in player_shell_source
    assert "human_controlled" in player_shell_source
    assert "CharacterControlMode" in bridge_source
    assert "CharacterLocomotionExecutionMode" in replica_source
    assert "CharacterPresentationInput" in replica_source
