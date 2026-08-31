from __future__ import annotations

from pathlib import Path

import pytest

from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry, GameplayPatchRuntimeError


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "inf-2" / "package-municipal-drought-services-v1.manifest.json"


def _manifest() -> GameplayPatchManifest:
    return GameplayPatchManifest.model_validate_json(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_frozen_municipal_drought_assessment_package_has_exact_v2_content_and_digest_pins() -> None:
    manifest = _manifest()
    extension = manifest.platform_extension

    assert manifest.manifest_schema_version == 2
    assert manifest.patch_revision_id == "package:municipal-drought-services:v1"
    assert manifest.content_digest == "sha256:8ac0cc29e02707f8954953133533b61341fd0d60f0ddf994d7dd3a9a72ed975e"
    assert manifest.expected_content_digest() == manifest.content_digest
    assert len(manifest.economic_outcomes) == 1
    outcome = manifest.economic_outcomes[0]
    assert (
        outcome.outcome_ref,
        outcome.typed_service_ref,
        outcome.source_evidence_mode,
        outcome.source_owner_ref,
        outcome.price_policy.fixed_amount,
        outcome.price_policy.currency_ref,
    ) == (
        "outcome:municipal-drought-assessment-settlement@1",
        "service:municipal-drought-assessment@1",
        "completed_service@1",
        "actor_gameplay.contract_domain",
        12,
        "currency:local",
    )
    assert extension is not None
    assert extension.outcome_declarations[0].declaration_digest == "sha256:d4790f64dbb739bb748a9d62378ce5b68622649a51a0ff1ea1a96e881f145bed"
    assert extension.capability_binding_requests == ()


def test_frozen_package_activates_as_immutable_v2_content_and_tampering_is_zero_write() -> None:
    manifest = _manifest()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))

    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))
    before = registry.export_snapshot()
    tampered = manifest.model_copy(update={"content_digest": "sha256:" + "0" * 64})

    assert active.patch_revision_ids == (manifest.patch_revision_id,)
    assert active.capability_bindings == ()
    with pytest.raises(GameplayPatchRuntimeError, match="patch_digest_mismatch"):
        registry.install(tampered)
    assert registry.export_snapshot() == before
