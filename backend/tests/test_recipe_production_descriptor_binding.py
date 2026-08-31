from __future__ import annotations

import pytest

from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, OwnerOperationDescriptor
from app.gameplay.patch_runtime import (
    CapabilityBindingRequest,
    GameplayPatchManifest,
    GameplayPatchRegistry,
    GameplayPatchRuntimeError,
    OutcomeDeclarationAuthorInput,
    PackageDefinition,
    PackageIdentity,
    PlatformExtension,
    TypedReadRequirement,
    _canonical_digest,
)
from closed_generic_manifest_fixtures import load_manifest


PACKAGE_REVISION = "package:recipe-production-demo:v1"
CONTENT_DIGEST = "sha256:b012f6a95105a55ae284600e03562e5381ef537f89ed3c7e3df70c7b54a78e1d"
DECLARATION_REF = "declaration:recipe-production-demo@1"
BINDING_REF = "binding:recipe-production-demo@1"
CAPABILITY_REF = "capability:recipe-production@1"
OUTCOME_REF = "outcome:recipe-production@1"
DESCRIPTOR_REF = "descriptor:construction-recipe-production@1"


def _manifest(*, binding_ref: str = BINDING_REF) -> GameplayPatchManifest:
    key = "recipe-production-kiln-v1" if binding_ref == "binding:kiln-fired-brick@1" else "recipe-production-demo-v1"
    return load_manifest(key)


def test_recipe_production_catalog_fixes_construction_authority_coordinates() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:construction-recipe-production@1",
        contract_kind="settlement",
    )
    descriptor = GovernedAuthorityContractCatalog.require_descriptor(DESCRIPTOR_REF)

    assert contract.owner_ref == "actor_gameplay.construction_production_domain"
    assert contract.stream_patterns == ("gameplay:construction_production:{facility_ref}",)
    assert contract.event_types == (
        "gameplay.construction_production.run_started",
        "gameplay.construction_production.run_finished",
    )
    assert contract.projection_scope == "project"
    assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert contract.replay_reader_ref == "ConstructionProductionAuthority.projector"
    assert descriptor.allowed_predicate_family_refs == (
        "predicate:construction-facility-committed@1",
    )
    assert descriptor.allowed_proposal_effect_types == ("effect:recipe-production-run@1",)
    assert descriptor.allowed_recipe_family_refs == ("recipe_production@1",)
    assert descriptor.package_slot_refs == (
        "slot:duration@1",
        "slot:facility-definition@1",
        "slot:input-items@1",
        "slot:output-items@1",
        "slot:qualification@1",
        "slot:recipe-definition@1",
    )


def test_recipe_production_binding_is_exact_one_and_replays_all_activation_pins() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(_manifest())
    active = registry.activate((PACKAGE_REVISION,))

    assert len(active.capability_bindings) == 1
    binding = active.capability_bindings[0]
    assert binding.binding_ref == BINDING_REF
    assert binding.package_revision == PACKAGE_REVISION
    assert binding.descriptor_ref == DESCRIPTOR_REF
    assert binding.descriptor_revision == DESCRIPTOR_REF
    assert binding.active_patch_set_revision == active.active_patch_set_revision
    snapshot_binding = registry.export_snapshot()["active_patch_set"]["capability_bindings"][0]
    assert {
        key: snapshot_binding[key]
        for key in (
            "binding_ref",
            "package_revision",
            "content_digest",
            "declaration_digest",
            "descriptor_ref",
            "descriptor_revision",
            "active_patch_set_revision",
        )
    } == {
        "binding_ref": BINDING_REF,
        "package_revision": PACKAGE_REVISION,
        "content_digest": registry.candidate(PACKAGE_REVISION).content_digest,
        "declaration_digest": binding.declaration_digest,
        "descriptor_ref": DESCRIPTOR_REF,
        "descriptor_revision": DESCRIPTOR_REF,
        "active_patch_set_revision": active.active_patch_set_revision,
    }

    replayed = GameplayPatchRegistry.from_snapshot(
        registry.export_snapshot(), trusted_authors=frozenset({"author:repo"})
    )
    assert replayed.active_patch_set == active
    assert replayed.active_manifests(active.active_patch_set_revision)[0].patch_revision_id == PACKAGE_REVISION


def test_recipe_production_activation_pins_the_canonical_typed_family_content_digest() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    manifest = _manifest()
    registry.install(manifest)
    active = registry.activate((PACKAGE_REVISION,))

    extension = manifest.platform_extension
    assert extension is not None
    declaration = extension.outcome_declarations[0]
    definition = extension.package_definitions[0]
    binding = active.capability_bindings[0]

    assert binding.family_ref == "recipe_production@1"
    assert binding.declaration_ref == declaration.declaration_ref
    assert binding.definition_ref == definition.definition_ref
    assert binding.family_content_digest == _canonical_digest(definition.typed_content)


def test_recipe_production_activation_rejects_tampered_declaration_digest() -> None:
    manifest = _manifest()
    extension = manifest.platform_extension
    assert extension is not None
    declaration = extension.outcome_declarations[0].model_copy(
        update={"declaration_digest": "sha256:" + "f" * 64}
    )
    tampered_extension = extension.model_copy(
        update={"outcome_declarations": (declaration,)},
        deep=True,
    )
    tampered_manifest = manifest.model_copy(
        update={"platform_extension": tampered_extension},
        deep=True,
    )
    tampered_manifest = tampered_manifest.model_copy(
        update={"content_digest": tampered_manifest.expected_content_digest()}
    )

    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(tampered_manifest)

    with pytest.raises(
        GameplayPatchRuntimeError,
        match="patch_capability_binding_declaration_digest_mismatch",
    ):
        registry.activate((PACKAGE_REVISION,))
    assert registry.active_patch_set is None


def test_recipe_production_activation_rejects_tampered_candidate_content_digest() -> None:
    manifest = _manifest()
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(manifest)
    registry._candidates[PACKAGE_REVISION] = manifest.model_copy(  # noqa: SLF001
        update={"content_digest": "sha256:" + "f" * 64}
    )

    with pytest.raises(
        GameplayPatchRuntimeError,
        match="patch_capability_binding_content_digest_mismatch",
    ):
        registry.activate((PACKAGE_REVISION,))
    assert registry.active_patch_set is None


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("unknown", "patch_capability_binding_unknown"),
        ("multiple", "patch_capability_binding_ambiguous"),
        ("mismatch", "patch_capability_binding_mismatch"),
    ],
)
def test_recipe_production_binding_failures_do_not_mutate_active_set(
    monkeypatch: pytest.MonkeyPatch, mutation: str, error: str
) -> None:
    catalog_descriptors = GovernedAuthorityContractCatalog.descriptors()
    target = OwnerOperationDescriptor(
        descriptor_ref=DESCRIPTOR_REF,
        descriptor_revision=DESCRIPTOR_REF,
        capability_ref=CAPABILITY_REF,
        outcome_family_ref=OUTCOME_REF,
        allowed_predicate_family_refs=("predicate:construction-facility-committed@1",),
        allowed_proposal_effect_types=("effect:recipe-production-run@1",),
        allowed_recipe_family_refs=("recipe_production@1",),
        package_slot_refs=(
            "slot:duration@1",
            "slot:facility-definition@1",
            "slot:input-items@1",
            "slot:output-items@1",
            "slot:qualification@1",
            "slot:recipe-definition@1",
        ),
    )
    base_descriptors = tuple(item for item in catalog_descriptors if item.descriptor_ref != DESCRIPTOR_REF)
    if mutation == "unknown":
        descriptors = base_descriptors
    elif mutation == "multiple":
        descriptors = base_descriptors + (target,
            target.model_copy(
                update={
                    "descriptor_ref": "descriptor:recipe-production@2",
                    "descriptor_revision": "descriptor:recipe-production@2",
                }
            ),
        )
    else:
        descriptors = base_descriptors + (target.model_copy(update={"outcome_family_ref": "outcome:other@1"}),)
    monkeypatch.setattr(
        GovernedAuthorityContractCatalog, "descriptors", staticmethod(lambda: descriptors)
    )

    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(_manifest())
    before = registry.active_patch_set
    with pytest.raises(GameplayPatchRuntimeError, match=error):
        registry.activate((PACKAGE_REVISION,))
    assert registry.active_patch_set is before


def test_recipe_production_duplicate_family_requests_fail_before_active_set_mutation() -> None:
    manifest = _manifest()
    extension = manifest.platform_extension
    assert extension is not None
    duplicate_request = extension.capability_binding_requests[0]
    duplicate_extension = extension.model_copy(
        update={
            "capability_binding_requests": (
                *extension.capability_binding_requests,
                duplicate_request,
            )
        },
        deep=True,
    )
    duplicate_manifest = manifest.model_copy(
        update={"platform_extension": duplicate_extension},
        deep=True,
    )
    duplicate_manifest = duplicate_manifest.model_copy(
        update={"content_digest": duplicate_manifest.expected_content_digest()}
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(duplicate_manifest)

    with pytest.raises(GameplayPatchRuntimeError, match="patch_capability_binding_ambiguous"):
        registry.activate((PACKAGE_REVISION,))
    assert registry.active_patch_set is None


def test_recipe_production_malformed_content_fails_before_active_set_mutation() -> None:
    manifest = _manifest()
    extension = manifest.platform_extension
    assert extension is not None
    definition = extension.package_definitions[0].model_copy(
        update={"typed_content": {**extension.package_definitions[0].typed_content, "owner_ref": "owner:caller@1"}}
    )
    malformed_extension = extension.model_copy(
        update={"package_definitions": (definition,)},
        deep=True,
    )
    malformed_manifest = manifest.model_copy(
        update={"platform_extension": malformed_extension},
        deep=True,
    )
    malformed_manifest = malformed_manifest.model_copy(
        update={"content_digest": malformed_manifest.expected_content_digest()}
    )
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(malformed_manifest)

    with pytest.raises(GameplayPatchRuntimeError, match="patch_capability_binding_content_invalid"):
        registry.activate((PACKAGE_REVISION,))
    assert registry.active_patch_set is None
