import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_presentation_asset_manifest_records_staged_packages_without_admitting_rejected_candidates() -> None:
    manifest_path = ROOT / "assets" / "characters" / "asset_manifests" / "character_presentation_bindings.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["contract"] == "character_presentation_bindings.v1"
    bindings = {binding["package_id"]: binding for binding in manifest["bindings"]}
    assert set(bindings) == {"crusader_knight", "external_character_b"}
    assert bindings["crusader_knight"]["delivery_level"] == "full_body_action"
    assert bindings["external_character_b"]["admission"] == "rejected"
    assert all("actor_id" not in binding for binding in bindings.values())


def test_main_demo_mounts_the_presentation_asset_resolver() -> None:
    scene_source = (ROOT / "scenes" / "integration" / "Unified3DIntegrationValidation.tscn").read_text(encoding="utf-8")

    assert 'path="res://scripts/character/CharacterPresentationAssetResolver.gd"' in scene_source
    assert '[node name="CharacterPresentationAssetResolver" type="Node" parent="."]' in scene_source
    assert "character_presentation_bindings.json" in scene_source


def test_resolver_only_applies_approved_bindings_through_the_character_replica_contract() -> None:
    resolver_source = (ROOT / "scripts" / "character" / "CharacterPresentationAssetResolver.gd").read_text(encoding="utf-8")
    replica_source = (ROOT / "scripts" / "character" / "CharacterReplica.gd").read_text(encoding="utf-8")

    assert "character_presentation_bindings.v1" in resolver_source
    assert 'binding_status", "candidate"' in resolver_source
    assert 'binding_status != "approved"' in resolver_source
    assert "apply_presentation_asset_binding" in resolver_source
    assert "func apply_presentation_asset_binding(binding: Dictionary) -> bool:" in replica_source
    assert "role_scene_ref" in replica_source
    assert "_fallback_role_asset_scene" in replica_source
