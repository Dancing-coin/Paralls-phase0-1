from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_motion_composition_has_one_command_boundary() -> None:
    contribution = _read("scripts/character/MotionContribution.gd")
    composer = _read("scripts/character/MotionContributionComposer.gd")
    command = _read("scripts/character/PhysicsMotionCommand.gd")
    assert "root_motion" in contribution and "runtime_correction" in contribution
    assert "func compose(frame" in composer
    assert "root_translation" in command and "physics_body" in command
    assert "class_name PhysicsMotionCommand" in command


def test_motor_consumes_commands_and_replica_has_no_direct_body_write() -> None:
    motor = _read("scripts/character/CharacterMotor.gd")
    replica = _read("scripts/character/CharacterReplica.gd")
    assert "func apply_physics_command" in motor
    assert "MotionContributionComposer" in motor
    assert "global_position +=" not in replica
    assert "global_position =" not in replica
    assert "global_basis =" not in replica
