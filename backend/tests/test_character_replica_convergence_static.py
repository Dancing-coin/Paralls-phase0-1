from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_retirement_matrix_accounts_for_phase0_provider_and_integration_callers():
    path = ROOT / "docs/character/character-replica-retirement-matrix-2026-09-29.md"
    match = re.search(r"```json\s*(\[.*?\])\s*```", path.read_text(encoding="utf-8"), re.DOTALL)
    assert match is not None
    rows = {row["caller_path"]: row for row in json.loads(match.group(1))}
    for caller in (
        "scenes/phase0/CharacterBase.tscn",
        "scenes/phase0/ValidationPlayerShell.tscn",
        "scenes/integration/Unified3DIntegrationValidation.tscn",
        "scripts/character/EmbodiedStateProvider.gd",
        "scripts/character/EmbodiedSkeletalStateProvider.gd",
        "scripts/player/PlayerShell.gd",
    ):
        assert caller in rows
        assert rows[caller]["compatibility_allowed"] is False
    route = rows["backend/app/models/embodied_interaction.py"]
    assert route["compatibility_allowed"] is False
    assert route["category"] == "authority"


def test_character_actor_is_the_only_runtime_host() -> None:
    actor = read("scripts/character/CharacterActor.gd")
    assert "class_name CharacterActor" in actor
    assert "func begin_embodied_control_frame(" in actor
    assert "func apply_embodied_pose_sync(" in actor
    assert "func clear_embodied_control_frame()" in actor
    assert "func _update_movement(" in actor


def test_character_replica_compatibility_assets_are_deleted_after_zero_caller_gate() -> None:
    for relative in (
        "scripts/character/CharacterReplica.gd",
        "scenes/phase0/CharacterReplica.tscn",
        "scenes/phase0/ValidationCharacterReplica.tscn",
    ):
        assert not (ROOT / relative).exists(), relative


def test_active_sources_do_not_import_deleted_character_replica_assets() -> None:
    forbidden = (
        "scripts/character/CharacterReplica.gd",
        "scenes/phase0/CharacterReplica.tscn",
        "scenes/phase0/ValidationCharacterReplica.tscn",
    )
    roots = (ROOT / "scenes", ROOT / "scripts", ROOT / "backend", ROOT / ".harness" / "profiles")
    historical = {
        "scripts/verification/CharacterReplicaForwardingProbe.gd",
        "scripts/verification/CharacterReplicaRetirementProbe.gd",
        "backend/tests/test_character_actor_scene_convergence_static.py",
        "backend/tests/test_character_motion_composition_contract.py",
        "backend/tests/test_character_replica_convergence_static.py",
        "backend/tests/test_character_scene_migration.py",
        "backend/tests/test_obj_archive_door_embodied_local_static.py",
        "scripts/verification/verify_character_replica_retirement.py",
        "scripts/presentation/character/CharacterReplica.gd",
        "backend/tests/test_character_motor_ownership_audit.py",
        "backend/tests/test_character_final_actor_contracts_static.py",
        "backend/tests/test_character_replica_forwarding_contract.py",
        "backend/tests/test_character_runtime_state_extraction_static.py",
    }
    offenders: list[str] = []
    for base in roots:
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".gd", ".tscn", ".py", ".json"}:
                continue
            source = path.read_text(encoding="utf-8", errors="ignore")
            if path.relative_to(ROOT).as_posix() in historical:
                continue
            if any(token in source for token in forbidden):
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == [], offenders


def test_active_runtime_surfaces_are_actor_only() -> None:
    active_paths = (
        "scenes/integration/UnifiedCharacterActionFoundation.tscn",
        "scenes/integration/Unified3DIntegrationValidation.tscn",
        "scenes/phase0/CharacterBase.tscn",
        "scenes/phase0/ValidationPlayerShell.tscn",
        "scripts/character/EmbodiedStateProvider.gd",
        "scripts/character/EmbodiedSkeletalStateProvider.gd",
        "scripts/interaction/ArchiveDoorEmbodiedActionHost.gd",
        "scripts/player/PlayerShell.gd",
        "scripts/phase0/MainDemoController.gd",
    )
    for path in active_paths:
        source = read(path)
        assert "CharacterReplica" not in source, path
        assert "legacy_character_replica" not in source, path


def test_retirement_report_records_zero_caller_gate() -> None:
    report = read("docs/character/character-replica-retirement-report-2026-09-29.md")
    for field in (
        "active_scene_instances=0",
        "runtime_replica_lookups=0",
        "compatibility_call_count=0",
        "direct_body_writers_outside_motor=0",
        "direct_animation_writers_outside_controller=0",
    ):
        assert field in report
    assert "final_state: retired" in report


def test_external_animation_components_are_present_and_bound():
    controller = read("scripts/character/RoleAnimationController.gd")
    sampler = read("scripts/character/RootMotionSampler.gd")
    skin = read("scripts/street_combat/StreetCharacterSkin.gd")
    assert "extends Node" in controller
    assert "AnimationNodeStateMachine" in controller
    assert "cross_fade_seconds" in controller
    assert "extends Node" in sampler
    assert ":root.x" in sampler
    assert "consume_delta()" in sampler
    assert "RoleAnimationControllerRef" in skin
    assert "RootMotionSamplerRef" in skin


def test_root_motion_is_motor_owned_and_exclusive():
    actor = read("scripts/character/CharacterActor.gd")
    motor = read("scripts/character/CharacterMotor.gd")
    skin = read("scripts/street_combat/StreetCharacterSkin.gd")
    assert 'command["root_motion_exclusive"]' in actor
    assert 'root_motion_exclusive' in motor
    assert "body.move_and_slide()" in motor
    assert "global_position +=" not in skin
    assert "move_and_slide(" not in skin


def test_street_locomotion_loops_and_actions_are_one_shot():
    controller = read("scripts/character/RoleAnimationController.gd")
    assert 'animation.loop_mode = Animation.LOOP_LINEAR' in controller
    assert 'animation.loop_mode = Animation.LOOP_NONE' in controller
    assert '"boxing"' in controller
    assert '"sword_attack"' in controller


def test_streetdemo_baseline_probe_is_bound_to_real_acceptance_scene():
    scene = read("scenes/phase0/StreetCombatDemo.tscn")
    controller = read("scripts/street_combat/StreetCombatDemo.gd")
    assert 'res://scripts/street_combat/StreetCombatDemo.gd' in scene
    assert 'CharacterActionFoundationBaselineProbeRef' in controller
    assert 'UnifiedCharacterActionFoundation.tscn' not in scene
