from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_root_motion_and_hybrid_modes_remain_motor_owned() -> None:
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )
    architecture_doc = (ROOT / "docs" / "character" / "character-actor-architecture.md").read_text(
        encoding="utf-8"
    )
    migration_doc = (ROOT / "docs" / "character" / "character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "body.velocity.x =" in motor_source
    assert "body.velocity.z =" in motor_source
    assert "move_and_slide(" in motor_source
    assert "_consume_role_root_motion_world_delta" in replica_source
    assert "last_root_motion_world_delta" in replica_source
    assert "consume_root_motion_delta" in skin_source
    assert "move_and_slide(" not in skin_source
    assert "global_position +=" not in skin_source
    assert "## Root-Motion Ownership Guard" in architecture_doc
    assert "CharacterMotor remains the only normal owner of baseline displacement" in architecture_doc
    assert "Future root-motion and hybrid work must be motor-owned" in architecture_doc
    assert "CharacterReplica direct root-motion displacement remains transitional" in migration_doc


def test_phase0_fallback_locomotion_uses_the_motor_and_reports_real_directional_motion() -> None:
    motor_source = (ROOT / "scripts" / "character" / "CharacterMotor.gd").read_text(
        encoding="utf-8"
    )
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    controller_source = (ROOT / "scripts" / "phase0" / "MainDemoController.gd").read_text(
        encoding="utf-8"
    )
    validation_scene = (ROOT / "scenes" / "phase0" / "ValidationCharacterReplica.tscn").read_text(
        encoding="utf-8"
    )

    assert "body.global_basis.x * move_local.x" in motor_source
    assert "world_move := body.global_basis.x * move_local.x - body.global_basis.z * move_local.y" in motor_source
    assert "forward_alignment=" in controller_source
    assert "patrol_motion_step" in replica_source
    assert '[node name="CharacterReplica" type="CharacterBody3D"]' in validation_scene
