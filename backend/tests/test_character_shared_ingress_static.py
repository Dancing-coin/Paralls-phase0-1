from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_human_agent_and_program_paths_use_the_adapter_family() -> None:
    player_shell_source = _read("scripts/player/PlayerShell.gd")
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert "HumanControllerAdapter" in player_shell_source
    assert "build_intent_frame" in player_shell_source

    assert "ProgramControllerAdapter" in player_bridge_source
    assert "build_intent_frame" in player_bridge_source

    assert "AgentControllerAdapter" not in replica_source
    runtime_state_source = _read("scripts/character/CharacterRuntimeState.gd")
    assert "build_intent_frame" in runtime_state_source
    assert "get_execution_payload_intent_frame" in replica_source


def test_shared_ingress_keeps_control_sources_on_one_actor_facing_family() -> None:
    player_shell_source = _read("scripts/player/PlayerShell.gd")
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")
    replica_source = _read("scripts/character/CharacterReplica.gd")

    assert '"controller_source": "human"' not in player_shell_source
    assert '"controller_source": "program"' not in player_bridge_source
    assert '"controller_source": "agent"' not in replica_source

    assert "CharacterControllerPort" in _read("scripts/character/HumanControllerAdapter.gd")
    assert "CharacterControllerPort" in _read("scripts/character/ProgramControllerAdapter.gd")
    assert "CharacterControllerPort" in _read("scripts/character/AgentControllerAdapter.gd")


def test_player_shell_human_ingress_keeps_explicit_intent_frame_fields() -> None:
    player_shell_source = _read("scripts/player/PlayerShell.gd")

    assert '"move_local": move_local' in player_shell_source
    assert '"look_local": Vector2(0.0, look_pitch)' in player_shell_source
    assert '"desired_facing_yaw": rotation.y' in player_shell_source
    assert '"gait": gait' in player_shell_source
    assert '"action": action' in player_shell_source


def test_player_shell_fallback_motion_state_consumes_normalized_intent_frame() -> None:
    player_shell_source = _read("scripts/player/PlayerShell.gd")

    assert "CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)" in player_shell_source
    assert "CharacterControllerPortRef.get_move_local(normalized_frame)" in player_shell_source
    assert "CharacterControllerPortRef.get_gait_name(normalized_frame)" in player_shell_source


def test_phase0_player_bridge_does_not_rewrite_normalized_human_intent_frame_identity() -> None:
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")

    assert 'current_intent_frame["control_mode"] = CharacterControlModeRef.HUMAN_CONTROLLED' not in player_bridge_source
    assert 'current_intent_frame["controller_source"] = "human"' not in player_bridge_source


def test_player_bridge_consumes_current_intent_frame_through_controller_port_normalization() -> None:
    player_bridge_source = _read("scripts/player/Phase0PlayerBridge.gd")

    assert "CharacterControllerPortRef.normalize_intent_frame(frame)" in player_bridge_source
    assert "var normalized_frame := CharacterControllerPortRef.normalize_intent_frame(current_intent_frame)" in player_bridge_source
