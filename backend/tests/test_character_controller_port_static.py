from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_character_controller_port_family_exists() -> None:
    port_source = _read("scripts/character/CharacterControllerPort.gd")
    human_source = _read("scripts/character/HumanControllerAdapter.gd")
    agent_source = _read("scripts/character/AgentControllerAdapter.gd")
    program_source = _read("scripts/character/ProgramControllerAdapter.gd")

    assert "class_name CharacterControllerPort" in port_source
    assert "class_name HumanControllerAdapter" in human_source
    assert "class_name AgentControllerAdapter" in agent_source
    assert "class_name ProgramControllerAdapter" in program_source


def test_controller_port_normalizes_shared_actor_intent_shape() -> None:
    port_source = _read("scripts/character/CharacterControllerPort.gd")

    assert "CharacterControlMode" in port_source
    assert "func normalize_intent_frame(candidate: Dictionary) -> Dictionary:" in port_source
    assert '"controller_source"' in port_source
    assert '"control_mode"' in port_source
    assert '"move_local"' in port_source
    assert '"look_local"' in port_source
    assert '"desired_facing_yaw"' in port_source
    assert '"stance"' in port_source
    assert '"gait"' in port_source
    assert '"action"' in port_source
    assert '"ttl_ms"' in port_source
    assert '"causation_id"' in port_source
    assert '"correlation_id"' in port_source


def test_adapters_route_through_controller_port_instead_of_unique_body_paths() -> None:
    human_source = _read("scripts/character/HumanControllerAdapter.gd")
    agent_source = _read("scripts/character/AgentControllerAdapter.gd")
    program_source = _read("scripts/character/ProgramControllerAdapter.gd")

    for source in [human_source, agent_source, program_source]:
        assert "CharacterControllerPort" in source
        assert "normalize_intent_frame" in source
        assert "build_intent_frame" in source

    assert '"controller_source": "human"' in human_source
    assert '"controller_source": "agent"' in agent_source
    assert '"controller_source": "program"' in program_source
