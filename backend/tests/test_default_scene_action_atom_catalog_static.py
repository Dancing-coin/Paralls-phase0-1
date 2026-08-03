from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_default_scene_atom_catalog_uses_the_existing_registry_contract() -> None:
    catalog = _read("scripts/character/DefaultSceneActionAtomCatalog.gd")
    registry = _read("scripts/character/CharacterEmbodimentAssetRegistry.gd")

    assert "class_name DefaultSceneActionAtomCatalog" in catalog
    assert "register_reviewed_action_catalog" in registry
    assert "inventory_reviewed_action_assets" in registry
    assert "CharacterActionAssetDescriptor.normalize" in registry
    assert "class_name CharacterEmbodimentAssetRegistry" not in catalog


def test_default_scene_atom_catalog_declares_reviewed_phase_bound_entries() -> None:
    catalog = _read("scripts/character/DefaultSceneActionAtomCatalog.gd")

    for action_tag in [
        "start_move",
        "turn_to_target",
        "raise_hand",
        "tap_contact",
        "recover_balance",
    ]:
        assert f'"action_tag": "{action_tag}"' in catalog
    for phase in ["plan_approach", "align", "prepare", "execute_contact", "recover"]:
        assert f'"controller_phase": "{phase}"' in catalog
    assert '"registration_keys"' in catalog
    assert '"animation_clip_ref"' in catalog
    assert '"reviewed": true' in catalog


def test_action_asset_registry_deduplicates_aliases_by_reviewed_atom() -> None:
    registry = _read("scripts/character/CharacterEmbodimentAssetRegistry.gd")

    assert "selected_action_tags" in registry
    assert "registration_keys" in registry
    assert "action_assets_unavailable" in registry
