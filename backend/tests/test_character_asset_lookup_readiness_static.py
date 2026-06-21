from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_asset_contracts_have_a_near_term_lookup_readiness_gate() -> None:
    asset_doc = (ROOT / "docs" / "character" / "character-asset-integration.md").read_text(
        encoding="utf-8"
    )
    migration_doc = (ROOT / "docs" / "character" / "character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "## Near-Term Asset Lookup Readiness Gate" in asset_doc
    assert "`CharacterAssetBindingProfile`" in asset_doc
    assert "`CharacterEquipmentBindingProfile`" in asset_doc
    assert "`CharacterActionAssetDescriptor`" in asset_doc
    assert "contract-only in this near-term cleanup" in migration_doc
    assert (ROOT / "scripts" / "character" / "CharacterAssetBindingProfile.gd").exists()
    assert (ROOT / "scripts" / "character" / "CharacterEquipmentBindingProfile.gd").exists()
    assert (ROOT / "scripts" / "character" / "CharacterActionAssetDescriptor.gd").exists()
    assert not (ROOT / "scripts" / "character" / "CharacterAssetLibrary.gd").exists()
