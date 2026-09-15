from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_contact_evidence_is_local_only_and_motor_owned() -> None:
    evidence = _read("scripts/character/PhysicsContactEvidence.gd")
    motor = _read("scripts/character/CharacterMotor.gd")
    assert "local_only" in evidence
    assert "func collect_contact_evidence" in motor
    assert "PhysicsContactEvidence" in motor


def test_root_policy_and_recovery_do_not_settle_world_truth() -> None:
    composer = _read("scripts/character/MotionContributionComposer.gd")
    controller = _read("scripts/interaction/EmbodiedActionController.gd")
    for policy in ("hold", "bounded_continue", "reversible_continue"):
        assert '"%s"' % policy in composer
    assert "apply_authority_recovery" in controller
    assert "GameplayEventStore" not in controller
