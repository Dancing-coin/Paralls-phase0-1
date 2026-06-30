from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_character_asset_runtime_declares_registry_and_preload_api() -> None:
    text = (ROOT / "scripts" / "character" / "CharacterEmbodimentAssetRuntime.gd").read_text(
        encoding="utf-8"
    )

    assert "register_motion_asset" in text
    assert "preload_assets_for_semantics" in text
def test_character_asset_runtime_declares_realization_plan_api() -> None:
    text = (ROOT / "scripts" / "character" / "CharacterEmbodimentAssetRuntime.gd").read_text(
        encoding="utf-8"
    )

    assert "compose_realization_plan" in text
    assert "missing_semantic_keys" in text
    assert "generated_motion_allowed" in text
