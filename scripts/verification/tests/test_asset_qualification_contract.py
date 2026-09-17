from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_character_qualification_scene_and_runner_exist() -> None:
    assert (ROOT / "scenes" / "qualification" / "CharacterAssetQualification.tscn").is_file()
    assert (ROOT / "scripts" / "qualification" / "CharacterAssetQualificationRunner.gd").is_file()


def test_environment_qualification_scene_and_runner_exist() -> None:
    assert (ROOT / "scenes" / "qualification" / "EnvironmentAssetQualification.tscn").is_file()
    assert (ROOT / "scripts" / "qualification" / "EnvironmentAssetQualificationRunner.gd").is_file()


def test_character_qualification_manifest_declares_hard_capabilities() -> None:
    manifest_path = ROOT / "assets" / "validation" / "manifests" / "character-qualification.example.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["contract"] == "character_asset_qualification.v1"
    assert "required_bone_groups" in manifest
    assert "required_action_tags" in manifest
    assert "required_role_methods" in manifest
    assert manifest["qualification_status"] == "candidate"


def test_asset_activation_uses_active_pack_paths() -> None:
    source = (ROOT / "tools" / "asset_activation.py").read_text(encoding="utf-8")
    assert "assets/active/" in source
    assert "archive/" in source
