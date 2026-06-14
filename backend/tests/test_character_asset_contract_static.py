from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_character_asset_binding_profile_contract_exists() -> None:
    source = _read("scripts/character/CharacterAssetBindingProfile.gd")

    assert "class_name CharacterAssetBindingProfile" in source
    assert '"role_asset_id"' in source
    assert '"skeleton_profile_id"' in source
    assert '"equipment_slots"' in source
    assert '"supported_action_tags"' in source
    assert '"compatibility_level"' in source


def test_character_equipment_binding_profile_contract_exists() -> None:
    source = _read("scripts/character/CharacterEquipmentBindingProfile.gd")

    assert "class_name CharacterEquipmentBindingProfile" in source
    assert '"slots"' in source
    assert '"slot_anchor_paths"' in source
    assert '"offset_defaults"' in source
    assert '"visibility_rules"' in source


def test_character_action_asset_descriptor_contract_exists() -> None:
    source = _read("scripts/character/CharacterActionAssetDescriptor.gd")

    assert "class_name CharacterActionAssetDescriptor" in source
    assert '"action_tag"' in source
    assert '"animation_clip_ref"' in source
    assert '"root_motion_profile"' in source
    assert '"modifier_profile"' in source
    assert '"required_slots"' in source
    assert '"compatibility_level"' in source
