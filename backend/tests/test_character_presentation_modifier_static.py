from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_knight_role_skin_builds_modifier_input_but_does_not_write_equipment_pose() -> None:
    role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )

    assert "func _build_combat_modifier_input() -> Dictionary:" in role_skin_source
    assert "_sync_combat_modifier()" in role_skin_source
    assert "set_modifier_input" in role_skin_source
    assert "sword_in_hand.rotation =" not in role_skin_source
    assert "shield_in_hand.rotation =" not in role_skin_source


def test_knight_combat_modifier_consumes_modifier_input_and_owns_post_animation_pose() -> None:
    modifier_source = (ROOT / "scripts" / "character" / "KnightCombatModifier.gd").read_text(
        encoding="utf-8"
    )

    assert "func set_modifier_input(modifier_input: Dictionary) -> void:" in modifier_source
    assert "func _process_modification() -> void:" in modifier_source
    assert "func _apply_equipment_pose() -> void:" in modifier_source
    assert "sword_in_hand.rotation =" in modifier_source
    assert "shield_in_hand.rotation =" in modifier_source
    assert "func set_state(" not in modifier_source
    assert "func set_motion_profile(" not in modifier_source
