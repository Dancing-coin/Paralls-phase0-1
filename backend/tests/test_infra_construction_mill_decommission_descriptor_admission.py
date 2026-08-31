from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContractCatalog,
    OwnerOperationDescriptor,
)
from app.gameplay.patch_runtime import GameplayPatchRegistry, GameplayPatchRuntimeError


PACKAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "inf-1"
    / "package-industrial-facilities-v3-decommission.manifest.json"
)
PACKAGE_REVISION = "package:industrial-facilities:v3"
CONTENT_DIGEST = "sha256:bde53b49ee207d90c2d2bfd7e7ff95ef03638a41719883a21c2b83a3e15930ca"
DECLARATION_DIGEST = "sha256:ad800530f5e9a85baad29c5825a0e7edfc7e6cfa664a20208f5d2566819a7c3c"
BINDING_REF = "binding:industrial-facilities-mill-reinforced-decommission@1"
DESCRIPTOR_REF = "descriptor:construction-facility-mill-decommission@1"


def _manifest():
    from app.gameplay.patch_runtime import GameplayPatchManifest

    return GameplayPatchManifest.model_validate(json.loads(PACKAGE_PATH.read_text(encoding="utf-8")))


def _registry() -> GameplayPatchRegistry:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    registry.install(_manifest())
    return registry


def test_frozen_v3_binds_exactly_one_approved_descriptor_and_retains_all_activation_pins() -> None:
    manifest = _manifest()
    registry = _registry()

    active = registry.activate((PACKAGE_REVISION,))

    assert manifest.content_digest == CONTENT_DIGEST
    assert len(active.capability_bindings) == 1
    binding = active.capability_bindings[0]
    assert binding.binding_ref == BINDING_REF
    assert binding.package_revision == PACKAGE_REVISION
    assert binding.content_digest == CONTENT_DIGEST
    assert binding.declaration_digest == DECLARATION_DIGEST
    assert binding.descriptor_ref == DESCRIPTOR_REF
    assert binding.descriptor_revision == DESCRIPTOR_REF
    assert binding.active_patch_set_revision == active.active_patch_set_revision

    replayed = GameplayPatchRegistry.from_snapshot(
        registry.export_snapshot(), trusted_authors=frozenset({"author:repo"})
    )
    assert replayed.active_patch_set == active


def test_exact_catalog_row_is_lifecycle_only_and_uses_existing_construction_spine() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:construction-facility-mill-decommission@1",
        contract_kind="lifecycle",
    )
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref == DESCRIPTOR_REF
    )

    assert contract.owner_ref == "actor_gameplay.construction_production_domain"
    assert contract.stream_patterns == ("gameplay:construction_production:{facility_ref}",)
    assert contract.event_types == ("gameplay.construction_production.facility_decommissioned",)
    assert contract.projection_scope == "project"
    assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert contract.replay_reader_ref == "ConstructionProductionAuthority.projector"
    assert descriptor == OwnerOperationDescriptor(
        descriptor_ref=DESCRIPTOR_REF,
        descriptor_revision=DESCRIPTOR_REF,
        capability_ref="capability:construction-facility-mill-decommission@1",
        outcome_family_ref="outcome:construction-facility-mill-decommission@1",
        allowed_predicate_family_refs=("predicate:construction-facility-mill-reinforced@1",),
        allowed_proposal_effect_types=("effect:construction-facility-mill-decommission@1",),
    )


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("unknown", "patch_capability_binding_unknown"),
        ("multiple", "patch_capability_binding_ambiguous"),
        ("mismatch", "patch_capability_binding_mismatch"),
    ],
)
def test_unadmitted_multiple_or_mismatched_descriptor_fails_before_active_mutation(
    monkeypatch: pytest.MonkeyPatch, mutation: str, error: str
) -> None:
    catalog_descriptors = GovernedAuthorityContractCatalog.descriptors()
    target = next(item for item in catalog_descriptors if item.descriptor_ref == DESCRIPTOR_REF)
    if mutation == "unknown":
        descriptors = tuple(item for item in catalog_descriptors if item.descriptor_ref != DESCRIPTOR_REF)
    elif mutation == "multiple":
        descriptors = catalog_descriptors + (
            target.model_copy(
                update={
                    "descriptor_ref": "descriptor:construction-facility-mill-decommission@2",
                    "descriptor_revision": "descriptor:construction-facility-mill-decommission@2",
                }
            ),
        )
    else:
        descriptors = tuple(
            item.model_copy(update={"outcome_family_ref": "outcome:construction-other@1"})
            if item.descriptor_ref == DESCRIPTOR_REF
            else item
            for item in catalog_descriptors
        )
    monkeypatch.setattr(
        GovernedAuthorityContractCatalog, "descriptors", staticmethod(lambda: descriptors)
    )
    registry = _registry()
    before = registry.export_snapshot()

    with pytest.raises(GameplayPatchRuntimeError, match=error):
        registry.activate((PACKAGE_REVISION,))

    assert registry.export_snapshot() == before
