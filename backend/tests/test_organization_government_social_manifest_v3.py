from __future__ import annotations

import pytest

from app.gameplay.patch_runtime import GameplayPatchManifest


def _manifest(*, schema_version: int = 3, platform_version: str = "2.0") -> dict[str, object]:
    return {
        "manifest_schema_version": schema_version,
        "patch_id": "package:organization-government-social-platform",
        "patch_version": "3.0.0",
        "patch_revision_id": "package:organization-government-social-platform@3",
        "content_digest": "sha256:" + "0" * 64,
        "author_id": "author:repo",
        "trust_policy_ref": "trust:repo",
        "platform_extension": {
            "platform_schema_version": platform_version,
            "package_identity": {
                "package_id": "package:organization-government-social-platform",
                "package_version": "3.0.0",
                "package_revision": "package:organization-government-social-platform@3",
            },
            "package_definitions": [],
            "outcome_declarations": [],
            "capability_binding_requests": [],
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }


def test_ogs_manifest_uses_only_v3_platform_2_0_and_adapter_digest() -> None:
    manifest = GameplayPatchManifest.model_validate(_manifest())
    assert manifest.platform_extension is not None
    assert manifest.platform_extension.platform_schema_version == "2.0"
    assert manifest.expected_content_digest().startswith("sha256:")
    assert manifest.expected_content_digest() != manifest.content_digest


@pytest.mark.parametrize("schema_version, platform_version", ((2, "2.0"), (3, "1.0"), (3, "9.0")))
def test_ogs_manifest_rejects_noncanonical_schema_pair(schema_version: int, platform_version: str) -> None:
    with pytest.raises(ValueError, match="platform_schema_pair_invalid"):
        GameplayPatchManifest.model_validate(_manifest(schema_version=schema_version, platform_version=platform_version))
