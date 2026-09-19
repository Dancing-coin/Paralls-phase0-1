import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_presentation_asset_manifest_validates_candidate_and_approved_binding_contracts() -> None:
    manifest_path = ROOT / "assets" / "characters" / "asset_manifests" / "character_presentation_bindings.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["contract"] == "character_presentation_bindings.v1"
    bindings = manifest["bindings"]
    assert isinstance(bindings, list)
    assert {binding["package_id"] for binding in bindings} >= {"crusader_knight", "external_character_b"}
    approved_actor_ids = set()
    for binding in bindings:
        # 包资格报告不是 actor 绑定批准；缺省状态与 resolver 一样保持 candidate。
        binding_status = binding.get("binding_status", "candidate")
        assert binding_status in {"candidate", "approved", "rejected"}
        package_id = binding["package_id"]
        assert binding["manifest_ref"] == f"res://assets/active/{package_id}/manifest.json"
        assert binding["report_ref"] == f"assets/characters/qualification_reports/{package_id}.json"
        package = json.loads((ROOT / binding["manifest_ref"].removeprefix("res://")).read_text(encoding="utf-8"))
        report = json.loads((ROOT / binding["report_ref"]).read_text(encoding="utf-8"))
        assert package["contract"] == "character_action_asset_manifest.v1"
        assert report["contract"] == "character_qualification_report.v1"
        assert package["package_id"] == report["package_id"] == package_id
        assert binding["delivery_level"] == package["delivery_level"] == report["delivery_level"]
        digest = package["source"]["digest_sha256"].lower()
        assert report["source"]["digest_sha256"].lower() == digest
        assert report["provenance"]["package_digest"].lower() == digest
        assert package["provenance"]["package_digest"].lower() == digest
        if report["status"] == "rejected":
            assert binding["admission"] == "rejected"
            assert binding_status != "approved"
        if binding_status == "approved":
            assert report["status"] in {"qualified", "qualified_with_fallback"}
            assert binding.get("admission") != "rejected"
            actor_id = binding["actor_id"]
            assert isinstance(actor_id, str) and actor_id.strip()
            assert actor_id not in approved_actor_ids
            approved_actor_ids.add(actor_id)
            role_scene_ref = binding["visual_assets"]["role_scene_ref"]
            assert role_scene_ref.startswith("res://")
            role_scene = (ROOT / role_scene_ref.removeprefix("res://")).resolve()
            assert role_scene.is_relative_to(ROOT)
            assert role_scene.is_file()


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
