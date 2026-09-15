from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]

ACTIVE_ACTOR_SCRIPTS = (
    "scripts/character/CharacterMotor.gd",
    "scripts/character/CharacterReplica.gd",
    "scripts/player/PlayerShell.gd",
)


def find_actor_body_writers(paths: tuple[str, ...]) -> list[str]:
    """Return direct actor-body writes outside the Motor implementation."""
    forbidden = re.compile(r"\b(?:global_position|velocity)\b\s*(?:\+?=)|move_and_slide\s*\(")
    violations: list[str] = []
    for relative_path in paths:
        if relative_path.endswith("CharacterMotor.gd"):
            continue
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            if forbidden.search(line) and not line.lstrip().startswith("#"):
                violations.append(f"{relative_path}:{line_number}:{line.strip()}")
    return violations


def test_character_motor_owns_planar_displacement_path() -> None:
    player_shell_source = (ROOT / "scripts" / "player" / "PlayerShell.gd").read_text(encoding="utf-8")
    phase0_bridge_source = (ROOT / "scripts" / "player" / "Phase0PlayerBridge.gd").read_text(
        encoding="utf-8"
    )
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )

    assert player_shell_source.count("move_and_slide(") == 0
    assert "player.velocity.x =" not in phase0_bridge_source
    assert "player.velocity.z =" not in phase0_bridge_source
    assert motor_source.count("move_and_slide(") >= 1
    assert "body.velocity.x =" in motor_source
    assert "body.velocity.z =" in motor_source


def test_only_character_motor_owns_body_motion() -> None:
    assert find_actor_body_writers(ACTIVE_ACTOR_SCRIPTS) == []
