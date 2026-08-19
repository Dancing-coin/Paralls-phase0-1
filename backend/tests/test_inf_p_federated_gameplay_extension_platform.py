from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.gameplay.patch_runtime import (
    GameplayPatchManifest,
    GameplayPatchRegistry,
    GameplayPatchRuntimeError,
    _canonical_digest,
)
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.models import GameplayEvent
from app.gameplay.patch_lifecycle_authority import (
    GameplayPatchLifecycleProjector,
    GameplayPatchLifecycleReplayError,
)


def _declaration_payload() -> dict[str, object]:
    return {
        "declaration_ref": "declaration:platform-test@1",
        "outcome_family_ref": "outcome:platform-test@1",
        "definition_refs": ["definition:platform-test@1"],
        "eligibility_refs": ["construction:facility-acquired@1"],
        "policy_revision_ref": "policy:platform-test@1",
        "source_package_revision": "patch:platform-test@2.0.0",
    }


def _v2_payload(*, binding: bool = False, revision: str = "patch:platform-test@2.0.0") -> dict[str, object]:
    declaration = _declaration_payload()
    declaration["source_package_revision"] = revision
    declaration["declaration_digest"] = _canonical_digest(declaration)
    return {
        "manifest_schema_version": 2,
        "patch_id": "patch:platform-test",
        "patch_version": "2.0.0",
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
            "platform_schema_version": "1.0",
            "package_identity": {
                "package_id": "patch:platform-test",
                "package_version": "2.0.0",
                "package_revision": revision,
            },
            "package_definitions": [
                {
                    "definition_ref": "definition:platform-test@1",
                    "definition_schema_ref": "schema:platform-test@1",
                    "source_package_revision": revision,
                    "typed_content": {"label": "test"},
                }
            ],
            "outcome_declarations": [declaration],
            "capability_binding_requests": (
                [
                    {
                        "binding_ref": "binding:platform-test@1",
                        "capability_ref": "capability:platform-test@1",
                        "source_package_revision": revision,
                        "declaration_ref": "declaration:platform-test@1",
                        "typed_read_requirements": [],
                        "proposal_effect_types": [],
                    }
                ]
                if binding
                else []
            ),
            "dependency_and_conflict_refs": [],
            "replay_reader_refs": [],
            "verification_profile_refs": [],
        },
    }


def _v2_manifest(*, binding: bool = False, revision: str = "patch:platform-test@2.0.0") -> GameplayPatchManifest:
    candidate = GameplayPatchManifest.model_validate(_v2_payload(binding=binding, revision=revision))
    return candidate.model_copy(update={"content_digest": candidate.expected_content_digest()})


def test_v1_digest_bytes_remain_legacy_compatible_and_v1_cannot_carry_extension() -> None:
    legacy = GameplayPatchManifest(
        manifest_schema_version=1,
        patch_id="patch:legacy",
        patch_version="1.0.0",
        patch_revision_id="patch:legacy@1.0.0",
        content_digest="pending",
        author_id="author:repo",
        trust_policy_ref="trust:repo",
    )
    legacy_payload = legacy.model_dump(mode="json", exclude={"content_digest", "platform_extension"})
    legacy_payload.pop("economic_outcomes")

    assert legacy.expected_content_digest() == _canonical_digest(legacy_payload)

    invalid = legacy.model_dump(mode="json")
    invalid["platform_extension"] = {"platform_schema_version": "1.0"}
    with pytest.raises(ValidationError, match="platform_schema_pair_invalid"):
        GameplayPatchManifest.model_validate(invalid)


def test_v2_normalizes_declaration_digest_before_outer_digest_and_candidate_snapshot_replay() -> None:
    manifest = _v2_manifest()
    extension = manifest.platform_extension
    assert extension is not None
    normalized = extension.outcome_declarations[0]
    assert normalized.declaration_digest == _canonical_digest(_declaration_payload())
    assert manifest.expected_content_digest() == manifest.content_digest

    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))
    restored = GameplayPatchRegistry.from_snapshot(
        registry.export_snapshot(), trusted_authors=frozenset({"author:repo"})
    )

    assert restored.active_patch_set == active
    assert restored.candidate(manifest.patch_revision_id).content_digest == manifest.content_digest


@pytest.mark.parametrize(
    ("mutate", "error"),
    (
        (
            lambda payload: payload["platform_extension"]["outcome_declarations"][0].pop("declaration_digest"),
            "platform_declaration_digest_missing",
        ),
        (
            lambda payload: payload["platform_extension"]["outcome_declarations"][0].__setitem__("declaration_digest", "sha256:" + "0" * 64),
            "platform_declaration_digest_mismatch",
        ),
        (
            lambda payload: payload["platform_extension"]["package_definitions"].append(
                deepcopy(payload["platform_extension"]["package_definitions"][0])
            ),
            "platform_array_not_canonical",
        ),
        (
            lambda payload: payload["platform_extension"]["package_definitions"][0]["typed_content"].__setitem__("owner_ref", "authority:forged"),
            "platform_authority_shaped_payload",
        ),
    ),
)
def test_v2_malformed_digest_order_or_authority_payload_is_rejected_before_registry_write(mutate, error: str) -> None:
    payload = _v2_payload()
    mutate(payload)

    with pytest.raises(ValidationError, match=error):
        GameplayPatchManifest.model_validate(payload)


def test_v2_unknown_schema_pair_and_noncanonical_outer_arrays_are_rejected() -> None:
    payload = _v2_payload()
    payload["platform_extension"]["platform_schema_version"] = "1.1"
    with pytest.raises(ValidationError, match="platform_schema_pair_invalid"):
        GameplayPatchManifest.model_validate(payload)

    payload = _v2_payload()
    payload["requested_capabilities"] = [
        {"capability_id": "capability:z", "capability_version": "1", "call_sites": ["rule:z"], "reason": "test"},
        {"capability_id": "capability:a", "capability_version": "1", "call_sites": ["rule:a"], "reason": "test"},
    ]
    with pytest.raises(ValidationError, match="platform_array_not_canonical"):
        GameplayPatchManifest.model_validate(payload)


def test_complete_nonempty_binding_package_is_candidate_valid_but_unadmitted_binding_is_activation_zero_write() -> None:
    manifest = _v2_manifest(binding=True)
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)

    assert registry.candidate(manifest.patch_revision_id).content_digest == manifest.content_digest
    with pytest.raises(GameplayPatchRuntimeError, match="patch_capability_binding_unknown"):
        registry.activate((manifest.patch_revision_id,))
    assert registry.active_patch_set is None


@pytest.mark.parametrize(
    ("mutate", "error"),
    (
        (
            lambda payload: payload["platform_extension"]["capability_binding_requests"][0].__setitem__(
                "source_package_revision", "patch:other@2.0.0"
            ),
            "platform_package_revision_mismatch",
        ),
        (
            lambda payload: payload["platform_extension"]["capability_binding_requests"][0].__setitem__(
                "declaration_ref", "declaration:missing@1"
            ),
            "platform_binding_declaration_unknown",
        ),
    ),
)
def test_binding_structure_conflicts_are_rejected_before_candidate_write(mutate, error: str) -> None:
    payload = _v2_payload(binding=True)
    mutate(payload)

    with pytest.raises(ValidationError, match=error):
        GameplayPatchManifest.model_validate(payload)


def _platform_descriptor(*, descriptor_ref: str = "descriptor:platform-test@1", outcome_family_ref: str = "outcome:platform-test@1"):
    from app.gameplay.governed_contract_catalog import OwnerOperationDescriptor

    return OwnerOperationDescriptor(
        descriptor_ref=descriptor_ref,
        descriptor_revision="descriptor:platform-test@1",
        capability_ref="capability:platform-test@1",
        outcome_family_ref=outcome_family_ref,
        allowed_predicate_family_refs=(),
        allowed_proposal_effect_types=(),
    )


def test_activation_resolves_exactly_one_readonly_descriptor_and_persists_binding_pins(monkeypatch) -> None:
    descriptor = _platform_descriptor()
    monkeypatch.setattr(GovernedAuthorityContractCatalog, "descriptors", staticmethod(lambda: (descriptor,)))
    manifest = _v2_manifest(binding=True)
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)

    active = registry.activate((manifest.patch_revision_id,))
    binding = active.capability_bindings[0]
    assert binding.package_revision == manifest.patch_revision_id
    assert binding.content_digest == manifest.content_digest
    assert binding.declaration_digest == manifest.platform_extension.outcome_declarations[0].declaration_digest
    assert binding.descriptor_ref == descriptor.descriptor_ref
    assert binding.descriptor_revision == descriptor.descriptor_revision
    assert binding.active_patch_set_revision == active.active_patch_set_revision

    snapshot = registry.export_snapshot()
    active_snapshot = snapshot["active_patch_set"]
    assert isinstance(active_snapshot, dict)
    assert active_snapshot["capability_bindings"][0]["descriptor_revision"] == descriptor.descriptor_revision
    restored = GameplayPatchRegistry.from_snapshot(snapshot, trusted_authors=frozenset({"author:repo"}))
    assert restored.active_patch_set == active


@pytest.mark.parametrize(
    ("descriptors", "error"),
    (
        ((), "patch_capability_binding_unknown"),
        ((_platform_descriptor(), _platform_descriptor(descriptor_ref="descriptor:platform-test@2")), "patch_capability_binding_ambiguous"),
        ((_platform_descriptor(outcome_family_ref="outcome:other@1"),), "patch_capability_binding_mismatch"),
    ),
)
def test_unknown_multiple_or_mismatched_descriptor_rejects_activation_without_mutation(monkeypatch, descriptors, error: str) -> None:
    monkeypatch.setattr(GovernedAuthorityContractCatalog, "descriptors", staticmethod(lambda: descriptors))
    manifest = _v2_manifest(binding=True)
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    before = registry.export_snapshot()

    with pytest.raises(GameplayPatchRuntimeError, match=error):
        registry.activate((manifest.patch_revision_id,))
    assert registry.active_patch_set is None
    assert registry.export_snapshot() == before


def test_checkpoint_tail_candidate_replay_retains_binding_pins(monkeypatch) -> None:
    descriptor = _platform_descriptor()
    monkeypatch.setattr(GovernedAuthorityContractCatalog, "descriptors", staticmethod(lambda: (descriptor,)))
    first = _v2_manifest(binding=True)
    second = _v2_manifest(binding=True, revision="patch:platform-tail@2.0.0")
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(first)
    checkpoint = registry.export_snapshot()
    restored = GameplayPatchRegistry.from_snapshot(checkpoint, trusted_authors=frozenset({"author:repo"}))
    restored.install(second)
    active = restored.activate((first.patch_revision_id, second.patch_revision_id))

    assert [item.package_revision for item in active.capability_bindings] == sorted(
        (first.patch_revision_id, second.patch_revision_id)
    )
    assert all(item.active_patch_set_revision == active.active_patch_set_revision for item in active.capability_bindings)

    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    assert registry.export_snapshot()["candidates"] == []


def test_lifecycle_replay_requires_persisted_activation_binding_pins(monkeypatch) -> None:
    descriptor = _platform_descriptor()
    monkeypatch.setattr(GovernedAuthorityContractCatalog, "descriptors", staticmethod(lambda: (descriptor,)))
    manifest = _v2_manifest(binding=True)
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    active = registry.compose_active_set((manifest.patch_revision_id,))
    bindings = [
        {
            "binding_ref": item.binding_ref,
            "package_revision": item.package_revision,
            "content_digest": item.content_digest,
            "declaration_digest": item.declaration_digest,
            "descriptor_ref": item.descriptor_ref,
            "descriptor_revision": item.descriptor_revision,
            "active_patch_set_revision": item.active_patch_set_revision,
        }
        for item in active.capability_bindings
    ]
    events = [
        GameplayEvent(
            event_id="event:candidate",
            event_type="gameplay.patch.candidate_installed",
            schema_version=1,
            stream_id="gameplay:patch-lifecycle",
            stream_revision=1,
            global_sequence=1,
            transaction_id="tx:platform",
            command_id="cmd:platform",
            causation_id="cause:platform",
            correlation_id="corr:platform",
            visibility_policy="authority_only",
            payload={"patch_revision_id": manifest.patch_revision_id, "content_digest": manifest.content_digest},
        ),
        GameplayEvent(
            event_id="event:activated",
            event_type="gameplay.patch.active_set_activated",
            schema_version=1,
            stream_id="gameplay:patch-lifecycle",
            stream_revision=2,
            global_sequence=2,
            transaction_id="tx:platform",
            command_id="cmd:platform",
            causation_id="cause:platform",
            correlation_id="corr:platform",
            visibility_policy="authority_only",
            payload={
                "next_patch_revision_ids": [manifest.patch_revision_id],
                "next_active_patch_set_revision": active.active_patch_set_revision,
                "capability_bindings": bindings,
            },
        ),
    ]

    rebuilt = GameplayPatchLifecycleProjector(registry=registry).rebuild(events)
    assert rebuilt.active_patch_set == active

    tampered = [event.model_copy(deep=True) for event in events]
    tampered[1].payload["capability_bindings"][0]["descriptor_revision"] = "descriptor:forged@1"
    with pytest.raises(GameplayPatchLifecycleReplayError, match="patch_lifecycle_capability_binding_mismatch"):
        GameplayPatchLifecycleProjector(registry=registry).rebuild(tampered)
