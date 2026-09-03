import pytest

from app.gameplay.patch_runtime import GameplayPatchManifest


def _manifest(**overrides):
    value = {
        "manifest_schema_version": 3,
        "patch_id": "patch:economy-platform",
        "patch_version": "3.0.0",
        "patch_revision_id": "patch:economy-platform@3",
        "content_digest": "sha256:" + "0" * 64,
        "author_id": "author:repo",
        "trust_policy_ref": "trust:repo",
        "platform_extension": {
            "platform_schema_version": "2.0",
            "package_identity": {
                "package_id": "patch:economy-platform",
                "package_version": "3.0.0",
                "package_revision": "patch:economy-platform@3",
            },
            "package_definitions": [],
            "outcome_declarations": [],
            "capability_binding_requests": [],
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }
    value.update(overrides)
    return value


def test_manifest_v3_accepts_platform_2_0_pairing():
    manifest = GameplayPatchManifest.model_validate(_manifest())
    assert manifest.manifest_schema_version == 3
    assert manifest.platform_extension is not None
    assert manifest.platform_extension.platform_schema_version == "2.0"


@pytest.mark.parametrize(
    "manifest_version, platform_version",
    [(2, "2.0"), (3, "1.0"), (3, "3.0")],
)
def test_manifest_rejects_invalid_v3_platform_pairings(manifest_version, platform_version):
    payload = _manifest(manifest_schema_version=manifest_version)
    payload["platform_extension"]["platform_schema_version"] = platform_version
    with pytest.raises(ValueError, match="platform_schema_pair_invalid"):
        GameplayPatchManifest.model_validate(payload)


def test_manifest_v3_content_digest_excludes_only_content_digest():
    manifest = GameplayPatchManifest.model_validate(_manifest())
    assert manifest.expected_content_digest().startswith("sha256:")
    assert manifest.expected_content_digest() != manifest.content_digest

