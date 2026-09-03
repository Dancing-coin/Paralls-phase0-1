from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.gameplay.patch_runtime import GameplayPatchManifest, _canonical_digest


def _declaration_payload() -> dict[str, object]:
    return {
        "declaration_ref": "declaration:econom-test@1",
        "outcome_family_ref": "outcome:econom-test@1",
        "definition_refs": ["definition:econom-test@1"],
        "eligibility_refs": ["predicate:econom-test@1"],
        "policy_revision_ref": "policy:econom-test@1",
        "source_package_revision": "patch:econom-test@3.0.0",
    }


def _v3_payload(*, revision: str = "patch:econom-test@3.0.0") -> dict[str, object]:
    declaration = _declaration_payload()
    declaration["source_package_revision"] = revision
    declaration["declaration_digest"] = _canonical_digest(declaration)
    return {
        "manifest_schema_version": 3,
        "patch_id": "patch:econom-test",
        "patch_version": "3.0.0",
        "patch_revision_id": revision,
        "content_digest": "pending",
        "author_id": "author:repo",
        "trust_policy_ref": "trust:repo",
        "dependencies": [],
        "state_group_ids": [],
        "state_group_migrations": [],
        "event_schemas": [],
        "rules": [],
        "requested_capabilities": [],
        "economic_outcomes": [],
        "granted_effect_types": [],
        "verification_profiles": [],
        "platform_extension": {
            "platform_schema_version": "2.0",
            "package_identity": {
                "package_id": "patch:econom-test",
                "package_version": "3.0.0",
                "package_revision": revision,
            },
            "package_definitions": [
                {
                    "definition_ref": "definition:econom-test@1",
                    "definition_schema_ref": "schema:econom-test@1",
                    "source_package_revision": revision,
                    "typed_content": {"label": "test"},
                }
            ],
            "outcome_declarations": [declaration],
            "capability_binding_requests": [],
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }


def test_v3_pair_accepts_platform_2_0_and_keeps_digest_canonical() -> None:
    manifest = GameplayPatchManifest.model_validate(_v3_payload())

    assert manifest.platform_extension is not None
    assert manifest.platform_extension.platform_schema_version == "2.0"
    normalized = manifest.model_copy(update={"content_digest": manifest.expected_content_digest()})
    assert normalized.expected_content_digest() == normalized.content_digest


@pytest.mark.parametrize(
    ("manifest_schema_version", "platform_schema_version"),
    (
        (3, "1.0"),
        (2, "2.0"),
        (1, "2.0"),
    ),
)
def test_v3_pair_rejects_other_schema_combinations(
    manifest_schema_version: int, platform_schema_version: str
) -> None:
    payload = _v3_payload()
    payload["manifest_schema_version"] = manifest_schema_version
    payload["platform_extension"]["platform_schema_version"] = platform_schema_version

    with pytest.raises(ValidationError, match="platform_schema_pair_invalid"):
        GameplayPatchManifest.model_validate(payload)


def test_v3_outer_arrays_must_stay_canonical() -> None:
    payload = _v3_payload()
    payload["requested_capabilities"] = [
        {"capability_id": "capability:z", "capability_version": "1", "call_sites": ["rule:z"], "reason": "test"},
        {"capability_id": "capability:a", "capability_version": "1", "call_sites": ["rule:a"], "reason": "test"},
    ]

    with pytest.raises(ValidationError, match="platform_array_not_canonical"):
        GameplayPatchManifest.model_validate(payload)
