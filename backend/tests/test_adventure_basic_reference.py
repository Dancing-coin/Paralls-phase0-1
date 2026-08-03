from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gameplay.adventure_basic_reference import load_adventure_basic_manifest
from app.gameplay.patch_runtime import GameplayPatchRuntimeError


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "gameplay" / "adventure-basic" / "manifest.json"


def test_adventure_basic_manifest_is_a_digest_valid_governed_reference_package() -> None:
    manifest = load_adventure_basic_manifest(_manifest_path())

    assert manifest.patch_id == "adventure-basic"
    assert manifest.patch_revision_id == "adventure-basic@0.1.0"
    assert "core.inventory" in manifest.state_group_ids
    assert manifest.verification_profiles == ("adventure-basic",)


def test_adventure_basic_manifest_rejects_tampering_before_activation(tmp_path: Path) -> None:
    payload = json.loads(_manifest_path().read_text(encoding="utf-8"))
    payload["state_group_ids"].append("core.unreviewed")
    tampered = tmp_path / "manifest.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(GameplayPatchRuntimeError, match="adventure_basic_manifest_digest_invalid"):
        load_adventure_basic_manifest(tampered)
