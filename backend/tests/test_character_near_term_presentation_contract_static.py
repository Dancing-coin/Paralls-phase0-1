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
    assert '"motion_state"' in role_skin_source
    assert '"action_state"' in role_skin_source
    assert '"equipment_state"' in role_skin_source
    assert "CharacterPresentationInput" in role_skin_source
    assert "_build_player_presentation_input" in replica_source
