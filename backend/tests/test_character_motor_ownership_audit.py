from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


GODOT_CANDIDATES = (
    Path(r"D:\godot\Godot_v4.6.3-stable_win64.exe"),
    Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe"),
)


def _godot() -> Path | None:
    configured = os.environ.get("GODOT_EXE")
    candidates = (Path(configured),) if configured else GODOT_CANDIDATES
    return next((path for path in candidates if path.exists()), None)

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


@pytest.mark.skipif(_godot() is None, reason="Godot executable is unavailable")
def test_motor_rejects_distinct_tokens_for_the_same_actor_tick_without_second_slide(tmp_path: Path) -> None:
    executable = _godot()
    assert executable is not None
    probe = tmp_path / "character_motor_same_tick_probe.gd"
    probe.write_text(
        """extends SceneTree
const Motor = preload(\"res://scripts/character/CharacterMotor.gd\")

func _initialize() -> void:
\t_run.call_deferred()

func _run() -> void:
\tvar body := CharacterBody3D.new()
\tvar collider := CollisionShape3D.new()
\tvar shape := SphereShape3D.new()
\tshape.radius = 0.2
\tcollider.shape = shape
\tbody.add_child(collider)
\troot.add_child(body)
\tvar motor := Motor.new()
\troot.add_child(motor)
\tawait physics_frame
\tvar first: Dictionary = motor.apply_physics_command(body, {\"actor_ref\": \"actor:test\", \"physics_tick\": 77, \"consumption_token\": \"token:a\", \"desired_velocity\": Vector3.ZERO, \"facing_yaw\": 0.0, \"root_delta\": Vector3.ZERO, \"impulse\": Vector3.ZERO, \"runtime_correction\": Vector3.ZERO, \"source_digest\": \"first\"}, 1.0 / 60.0)
\tvar duplicate: Dictionary = motor.apply_physics_command(body, {\"actor_ref\": \"actor:test\", \"physics_tick\": 77, \"consumption_token\": \"token:a\", \"desired_velocity\": Vector3.ZERO, \"facing_yaw\": 0.0, \"root_delta\": Vector3.ZERO, \"impulse\": Vector3.ZERO, \"runtime_correction\": Vector3.ZERO, \"source_digest\": \"duplicate\"}, 1.0 / 60.0)
\tvar second: Dictionary = motor.apply_physics_command(body, {\"actor_ref\": \"actor:test\", \"physics_tick\": 77, \"consumption_token\": \"token:b\", \"desired_velocity\": Vector3.ZERO, \"facing_yaw\": 0.0, \"root_delta\": Vector3.ZERO, \"impulse\": Vector3.ZERO, \"runtime_correction\": Vector3.ZERO, \"source_digest\": \"second\"}, 1.0 / 60.0)
\tvar stale: Dictionary = motor.apply_physics_command(body, {\"actor_ref\": \"actor:test\", \"physics_tick\": 76, \"consumption_token\": \"token:c\", \"desired_velocity\": Vector3.ZERO, \"facing_yaw\": 0.0, \"root_delta\": Vector3.ZERO, \"impulse\": Vector3.ZERO, \"runtime_correction\": Vector3.ZERO, \"source_digest\": \"stale\"}, 1.0 / 60.0)
\tprint(JSON.stringify({\"first_accepted\": first.get(\"accepted\", false), \"duplicate_accepted\": duplicate.get(\"accepted\", false), \"duplicate_reason\": duplicate.get(\"reason\", \"\"), \"second_accepted\": second.get(\"accepted\", false), \"second_reason\": second.get(\"reason\", \"\"), \"stale_accepted\": stale.get(\"accepted\", false), \"stale_reason\": stale.get(\"reason\", \"\"), \"body_revision\": motor.body_revision, \"last_tick\": motor.last_physics_tick}))
\tquit(0)
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(executable), "--headless", "--path", str(ROOT), "--script", str(probe)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["first_accepted"] is True
    assert payload["duplicate_accepted"] is False
    assert payload["duplicate_reason"] == "duplicate_consumption"
    assert payload["second_accepted"] is False
    assert payload["second_reason"] == "duplicate_physics_tick"
    assert payload["stale_accepted"] is False
    assert payload["stale_reason"] == "stale_physics_tick"
    assert payload["body_revision"] == 1
    assert payload["last_tick"] == 77
