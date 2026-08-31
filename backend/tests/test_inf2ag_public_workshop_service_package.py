from __future__ import annotations

from pathlib import Path

from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-2"
    / "package-industrial-facilities-v5-public-workshop-session.manifest.json"
)


def test_frozen_v5_public_workshop_package_has_exact_digest_and_service_content() -> None:
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    assert manifest.manifest_schema_version == 2
    assert manifest.patch_id == "package:industrial-facilities"
    assert manifest.patch_revision_id == "package:industrial-facilities:v5"
    assert manifest.patch_version == "5.0.0"
    assert manifest.content_digest == manifest.expected_content_digest()
    outcome = manifest.economic_outcomes[0]
    assert outcome.typed_service_ref == "service:industrial-facility-public-workshop-session@1"
    assert outcome.source_evidence_kind == "completed_service@1"
    assert outcome.price_policy.fixed_amount == 12
    assert outcome.price_policy.currency_ref == "currency:local"
    assert outcome.outcome_ref == "outcome:industrial-facility-public-workshop-session-settlement@1"


def test_v5_public_workshop_package_installs_immutably_and_tampering_is_zero_write() -> None:
    manifest = GameplayPatchManifest.model_validate_json(MANIFEST.read_text(encoding="utf-8"))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))
    before = registry.export_snapshot()
    tampered = manifest.model_copy(update={"content_digest": "sha256:" + "0" * 64})

    assert active.patch_revision_ids == (manifest.patch_revision_id,)
    try:
        registry.install(tampered)
    except Exception as exc:
        assert "patch_digest_mismatch" in str(exc)
    else:
        raise AssertionError("tampered package unexpectedly installed")
    assert registry.export_snapshot() == before
