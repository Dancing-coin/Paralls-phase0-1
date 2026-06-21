from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_near_term_presentation_input_contract_is_consumed_at_actor_to_skin_boundary() -> None:
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(
        encoding="utf-8"
    )
    role_skin_source = (ROOT / "scripts" / "character" / "KnightRoleSkin.gd").read_text(
        encoding="utf-8"
    )
    contract_source = (ROOT / "scripts" / "character" / "CharacterPresentationInput.gd").read_text(
        encoding="utf-8"
    )

    assert "PRESENTATION_INPUT_KEYS" in contract_source
    assert "get_motion_move_local_actual" in contract_source
    assert "get_motion_velocity_world" in contract_source
    assert "get_motion_gait_actual" in contract_source
    assert "get_requested_action" in contract_source
    assert "get_action_gait_hint" in contract_source
    assert "get_equipment_gait_hint" in contract_source
    assert "get_active_command_type" in contract_source
    assert "CharacterPresentationInput" in role_skin_source
    assert "CharacterPresentationInputRef.get_motion_move_local_actual(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_motion_velocity_world(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_motion_gait_actual(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_focus_target_id(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_requested_action(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_action_gait_hint(current_presentation_contract, presentation_gait)" in role_skin_source
    assert "CharacterPresentationInputRef.get_equipment_gait_hint(current_presentation_contract)" in role_skin_source
    assert "CharacterPresentationInputRef.get_active_command_type(current_presentation_contract)" in role_skin_source
    assert "_build_player_presentation_input" in replica_source
