from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.gameplay.closed_generic_gameplay_families import (
    CLOSED_FAMILY_GENERICITY_BLOCKERS,
    CLOSED_GAMEPLAY_FAMILIES,
    ClosedFamilyBinding,
    FacilityLifecycleTransitionContent,
    ProductionOutputCustodyContent,
    admit_family_binding,
    content_model_for_family,
    select_family_binding,
    family_binding_is_valid,
)
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.patch_runtime import GameplayPatchRuntimeError, GameplayPatchRegistry, PackageDefinition, _canonical_digest

EXPECTED_FAMILIES = (
    "recipe_production@1", "facility_identity_upgrade@1", "facility_lifecycle_transition@1",
    "production_output_certification@1", "production_output_custody@1", "declared_exchange@1",
    "fixed_service_exchange@1", "bounded_project_budget@1", "harvest_to_custody@1",
    "owner_bound_environment_consumer@1", "domain_acceptance_marker@1", "private_follow_on@1",
)


def test_closed_family_matrix_has_one_immutable_owner_contract_per_family() -> None:
    assert tuple(item.family_ref for item in CLOSED_GAMEPLAY_FAMILIES) == EXPECTED_FAMILIES
    assert len({item.contract_ref for item in CLOSED_GAMEPLAY_FAMILIES}) == len(EXPECTED_FAMILIES)
    assert len({item.descriptor_ref for item in CLOSED_GAMEPLAY_FAMILIES}) == len(EXPECTED_FAMILIES)
    for family in CLOSED_GAMEPLAY_FAMILIES:
        contract = GovernedAuthorityContractCatalog.require(contract_ref=family.contract_ref, contract_kind=family.contract_kind)
        descriptor = GovernedAuthorityContractCatalog.require_descriptor(family.descriptor_ref)
        assert contract.owner_ref == family.owner_ref
        assert contract.stream_patterns == (family.stream_pattern,)
        assert contract.event_types == family.event_types
        assert contract.projection_scope == family.privacy_scope
        assert descriptor.family_ref == family.family_ref
        assert descriptor.owner_ref == family.owner_ref
        assert descriptor.package_slot_refs == family.package_slot_refs


def test_closed_family_contracts_pin_family_specific_replay_readers() -> None:
    expected = {
        "recipe_production@1": "ConstructionProductionAuthority.projector",
        "facility_identity_upgrade@1": "ConstructionProductionAuthority.projector",
        "facility_lifecycle_transition@1": "ConstructionProductionAuthority.projector",
        "production_output_certification@1": "ConstructionProductionAuthority.projector",
            "production_output_custody@1": "InventoryAuthorityService.production_output_custody_view_for",
        "declared_exchange@1": "EconomyAuthorityService.declared_exchange_projection",
        "fixed_service_exchange@1": "EconomyAuthorityService.package_declared_negotiated_exchange_projection",
        "bounded_project_budget@1": "EconomyAuthorityService.public_project_budget_commitment_projection",
        "harvest_to_custody@1": "InventoryAuthorityService.harvest_to_custody_view_for",
        "owner_bound_environment_consumer@1": "SurvivalAuthority.projector",
        "domain_acceptance_marker@1": "OrganizationAuthority.domain_acceptance_marker_view_for",
        "private_follow_on@1": "SocialFactAuthority.public_milling_notice_social_acknowledgment_view_for",
    }
    for family_ref, reader_ref in expected.items():
        family = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == family_ref)
        contract = GovernedAuthorityContractCatalog.require(contract_ref=family.contract_ref, contract_kind=family.contract_kind)
        assert contract.replay_reader_ref == reader_ref


@pytest.mark.parametrize("family_ref", EXPECTED_FAMILIES)
def test_closed_family_content_models_are_frozen_and_reject_authority_coordinates(family_ref: str) -> None:
    model = content_model_for_family(family_ref)
    with pytest.raises(ValidationError):
        model.model_validate({"owner_ref": "caller"})
    assert model.model_config["frozen"] is True
    assert model.model_config["extra"] == "forbid"


def test_current_family_adapters_are_explicitly_classified() -> None:
    bounded = {item.family_ref for item in CLOSED_GAMEPLAY_FAMILIES if item.status == "bounded_adapter"}
    generic = {item.family_ref for item in CLOSED_GAMEPLAY_FAMILIES if item.status == "generic_implemented"}
    assert bounded == set()
    assert generic == set(EXPECTED_FAMILIES)
    assert {item.family_ref for item in CLOSED_FAMILY_GENERICITY_BLOCKERS} == bounded


def test_custody_family_is_explicitly_promoted_with_an_owner_bound_writer() -> None:
    custody = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == "production_output_custody@1")
    assert custody.status == "generic_implemented"
    assert custody.blocker_ref is None
    assert custody.adapter_ref == "InventoryAuthorityService.settle_production_output_custody"


def test_family_binding_selection_requires_exactly_one_candidate() -> None:
    binding = ClosedFamilyBinding(family_ref="recipe_production@1", package_revision="package:recipe@1", content_digest="sha256:" + "1" * 64, declaration_ref="declaration:recipe@1", declaration_digest="sha256:" + "2" * 64, descriptor_ref="descriptor:construction-recipe-production@1", descriptor_revision="descriptor:construction-recipe-production@1", active_set_revision="sha256:" + "3" * 64)
    assert select_family_binding((binding,)) is binding
    with pytest.raises(ValueError, match="closed_family_binding_zero"):
        select_family_binding(())
    with pytest.raises(ValueError, match="closed_family_binding_ambiguous"):
        select_family_binding((binding, binding.model_copy(update={"package_revision": "package:recipe@2"})))


def test_family_binding_admission_recomputes_content_and_declaration_digests() -> None:
    typed_content = {"facility_definition_ref": "definition:bakery@1", "facility_definition_schema_ref": "schema:facility@1", "facility_kind": "bakery", "recipe_ref": "recipe:bread@1", "recipe_schema_ref": "schema:recipe@1", "input_slots": [], "output_slots": [{"item_definition_ref": "item:bread@1", "quantity": 1, "unit": "loaf"}], "duration_ticks": 1, "qualification_refs": [], "policy_revision_ref": "policy:recipe@1"}
    declaration_payload = {"declaration_ref": "declaration:recipe@1", "outcome_family_ref": "outcome:recipe-production@1", "definition_refs": ["definition:bakery@1"], "eligibility_refs": [], "policy_revision_ref": "policy:recipe@1", "source_package_revision": "package:recipe@1"}
    with pytest.raises(ValueError, match="closed_family_content_digest_mismatch"):
        admit_family_binding(family_ref="recipe_production@1", package_revision="package:recipe@1", content_digest="sha256:" + "0" * 64, declaration_ref="declaration:recipe@1", declaration_digest=_canonical_digest(declaration_payload), declaration_payload=declaration_payload, descriptor_ref="descriptor:construction-recipe-production@1", descriptor_revision="descriptor:construction-recipe-production@1", active_set_revision="sha256:" + "2" * 64, typed_content=typed_content)


def test_family_binding_runtime_validation_requires_manifest_and_definition_pins() -> None:
    content = FacilityLifecycleTransitionContent(
        facility_definition_ref="definition:bakery-reinforced@1",
        facility_kind="bakery_reinforced",
        from_lifecycle="active",
        to_lifecycle="decommissioned",
        policy_revision_ref="policy:facility-lifecycle@1",
    )
    declaration_payload = {
        "declaration_ref": "declaration:lifecycle@1",
        "outcome_family_ref": "outcome:facility-lifecycle-transition@1",
        "definition_refs": ["definition:lifecycle@1"],
        "eligibility_refs": [],
        "policy_revision_ref": "policy:facility-lifecycle@1",
        "source_package_revision": "package:lifecycle@1",
    }
    definition = SimpleNamespace(
        definition_ref="definition:lifecycle@1",
        source_package_revision="package:lifecycle@1",
        typed_content=content.model_dump(mode="json"),
    )
    declaration = SimpleNamespace(
        declaration_ref="declaration:lifecycle@1",
        outcome_family_ref="outcome:facility-lifecycle-transition@1",
        source_package_revision="package:lifecycle@1",
        definition_refs=(definition.definition_ref,),
        declaration_digest=_canonical_digest(declaration_payload),
    )
    request = SimpleNamespace(
        capability_ref="capability:facility-lifecycle-transition@1",
        declaration_ref=declaration.declaration_ref,
        source_package_revision="package:lifecycle@1",
        typed_read_requirements=(SimpleNamespace(predicate_family_ref="predicate:construction-facility-acquired@1"),),
        proposal_effect_types=("effect:facility-lifecycle-transition@1",),
    )
    family = next(item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == "facility_lifecycle_transition@1")
    manifest = SimpleNamespace(patch_revision_id="package:lifecycle@1", content_digest="sha256:" + "a" * 64)
    binding = SimpleNamespace(
        family_ref=family.family_ref,
        package_revision=manifest.patch_revision_id,
        content_digest=manifest.content_digest,
        family_content_digest=_canonical_digest(content.model_dump(mode="json")),
        declaration_ref=declaration.declaration_ref,
        declaration_digest=declaration.declaration_digest,
        descriptor_ref=family.descriptor_ref,
        descriptor_revision=family.descriptor_ref,
        active_patch_set_revision="sha256:" + "b" * 64,
        definition_ref=definition.definition_ref,
    )
    assert family_binding_is_valid(
        family_ref=family.family_ref,
        manifest=manifest,
        declaration=declaration,
        declaration_payload=declaration_payload,
        request=request,
        definition=definition,
        binding=binding,
        active_set_revision=binding.active_patch_set_revision,
        typed_content=content,
    )
    assert not family_binding_is_valid(
        family_ref=family.family_ref,
        manifest=manifest,
        declaration=declaration,
        declaration_payload=declaration_payload,
        request=request,
        definition=definition,
        binding=binding.__class__(**{**binding.__dict__, "family_content_digest": "sha256:" + "c" * 64}),
        active_set_revision=binding.active_patch_set_revision,
        typed_content=content,
    )


def test_registry_accepts_admitted_custody_family_binding() -> None:
    content = ProductionOutputCustodyContent(output_item_definition_ref="item:bread@1", holder_binding_ref="binding:holder@1", container_binding_ref="binding:container@1", policy_revision_ref="policy:custody@1")
    definition = PackageDefinition(definition_ref="definition:custody@1", definition_schema_ref="schema:production-output-custody@1", source_package_revision="package:custody@1", typed_content=content.model_dump(mode="json"))
    declaration = SimpleNamespace(declaration_ref="declaration:custody@1", outcome_family_ref="outcome:production-output-custody@1", definition_refs=(definition.definition_ref,), declaration_digest="sha256:" + "1" * 64)
    request = SimpleNamespace(binding_ref="binding:custody@1", capability_ref="capability:production-output-custody@1", declaration_ref=declaration.declaration_ref, typed_read_requirements=(SimpleNamespace(predicate_family_ref="predicate:construction-production-output-certified@1"),), proposal_effect_types=("effect:production-output-custody@1",))
    manifest = SimpleNamespace(patch_revision_id="package:custody@1", content_digest="sha256:" + "2" * 64, platform_extension=SimpleNamespace(outcome_declarations=(declaration,), capability_binding_requests=(request,), package_definitions=(definition,)))
    bindings = GameplayPatchRegistry._resolve_capability_bindings((manifest,), "active-set@1")
    assert bindings[0].family_ref == "production_output_custody@1"
