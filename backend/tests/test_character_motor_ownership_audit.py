from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]

ACTIVE_ACTOR_SCRIPTS = (
    "scripts/character/CharacterMotor.gd",
    "scripts/character/CharacterActor.gd",
    "scripts/character/CharacterActor.gd",
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
            if relative_path.endswith("PlayerShell.gd") and "cam_holder.global_position" in line:
                continue
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


def test_street_combat_demo_does_not_write_body_velocity_or_call_slide():
    source = (ROOT / "scripts" / "street_combat" / "StreetCombatDemo.gd").read_text(encoding="utf-8")
    assert "player.velocity" not in source
    assert "player.global_position +=" not in source
    assert "player.global_position =" not in source
    assert "move_and_slide(" not in source


def test_motor_command_contains_physics_motion_ownership_fields():
    source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(encoding="utf-8")
    for field in ("desired_velocity", "impulse", "facing_yaw", "root_delta", "root_motion_exclusive", "physics_tick"):
        assert field in source
    assert "apply_physics_command" in source


def test_only_character_motor_calls_move_and_slide_in_active_scripts():
    active_paths = ACTIVE_ACTOR_SCRIPTS + ("scripts/street_combat/StreetCombatDemo.gd",)
    owners = []
    for relative_path in active_paths:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        if "move_and_slide(" in source:
            owners.append(relative_path)
    assert owners == ["scripts/character/CharacterMotor.gd"]


def test_root_motion_exclusive_command_suppresses_duplicate_locomotion():
    source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(encoding="utf-8")
    assert "if root_motion_exclusive:" in source
    assert "desired = Vector3.ZERO" in source
    composer = (ROOT / "scripts" / "character" / "CharacterActor.gd").read_text(encoding="utf-8")
    assert 'command["root_motion_exclusive"]' in composer
