from __future__ import annotations

import pytest

from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.organization_government_runtime import GovernmentAuthority, OrganizationAuthority
from app.gameplay.organization_government_social_content import (
    PopulationMaterializationPolicyContent,
    PopulationSignalContent,
    content_model_for_ogs_family,
)
from app.gameplay.organization_government_social_recipes import (
    OGSRecipeError,
    all_ogs_precompiled_recipes,
    validate_ogs_recipe_source,
)
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from test_organization_government_social_descriptor_binding import _manifest
from app.gameplay.patch_runtime import GameplayPatchRegistry


OGS_FAMILY_CASES = (
    (
        "organization_lifecycle@1",
        "actor_gameplay.organization_domain",
        "gameplay:organization:{organization_ref}",
        "gameplay.organization.lifecycle_transitioned@1",
        "project",
        ((OrganizationAuthority, "transition_admitted_platform_organization_lifecycle"),),
    ),
    (
        "organization_membership_delegation@1",
        "actor_gameplay.organization_domain",
        "gameplay:organization:{organization_ref}",
        "gameplay.organization.membership_delegation_recorded@1",
        "project",
        ((OrganizationAuthority, "record_admitted_platform_organization_membership"),),
    ),
    (
        "organization_operating_period@1",
        "actor_gameplay.organization_domain",
        "gameplay:organization:{organization_ref}",
        "gameplay.organization.operating_period_recorded@1",
        "project",
        ((OrganizationAuthority, "record_admitted_platform_organization_operating_period"),),
    ),
    (
        "organization_commitment_budget@1",
        "actor_gameplay.organization_domain",
        "gameplay:organization:{organization_ref}",
        "gameplay.organization.commitment_budget_proposed@1",
        "project",
        ((OrganizationAuthority, "record_admitted_platform_organization_commitment_budget"),),
    ),
    (
        "government_jurisdiction_policy@1",
        "actor_gameplay.government_domain",
        "gameplay:government:{jurisdiction_ref}",
        "gameplay.government.policy_lifecycle_recorded@1",
        "project",
        ((GovernmentAuthority, "record_admitted_platform_government_policy_lifecycle"),),
    ),
    (
        "government_permit_inspection_enforcement@1",
        "actor_gameplay.government_domain",
        "gameplay:government:case:{case_ref}",
        "gameplay.government.permit_inspection_case_recorded@1",
        "project",
        ((GovernmentAuthority, "record_admitted_platform_government_case"),),
    ),
    (
        "government_tax_treasury_project@1",
        "actor_gameplay.government_domain",
        "gameplay:government:{jurisdiction_ref}",
        "gameplay.government.tax_treasury_project_proposed@1",
        "authority_only",
        ((GovernmentAuthority, "record_admitted_platform_government_tax_project"),),
    ),
    (
        "government_notice_audit@1",
        "actor_gameplay.government_domain",
        "gameplay:government:{jurisdiction_ref}",
        "gameplay.government.notice_audit_recorded@1",
        "mixed",
        ((GovernmentAuthority, "record_admitted_platform_government_notice"),),
    ),
    (
        "social_identity_relationship@1",
        "authority:p5:social",
        "gameplay:social:relationship:{relationship_ref}",
        "gameplay.social.identity_relationship_recorded@1",
        "mixed",
        ((SocialFactAuthority, "record_admitted_platform_social_relationship"),),
    ),
    (
        "social_household_group@1",
        "authority:p5:social",
        "gameplay:social:group:{group_ref}",
        "gameplay.social.household_group_recorded@1",
        "project",
        ((SocialFactAuthority, "record_admitted_platform_social_group"),),
    ),
    (
        "social_norm_conflict@1",
        "authority:p5:social",
        "gameplay:social:case:{case_ref}",
        "gameplay.social.norm_conflict_recorded@1",
        "mixed",
        ((SocialFactAuthority, "record_admitted_platform_social_conflict"),),
    ),
    (
        "social_private_projection@1",
        "authority:p5:social",
        "gameplay:social:private:{participant_ref}",
        "gameplay.social.private_projection_recorded@1",
        "actor_private",
        ((SocialFactAuthority, "record_admitted_platform_social_private_projection"),),
    ),
    (
        "population_signal_materialization@1",
        "authority:p5:social",
        "gameplay:social:population:{signal_ref}",
        "gameplay.social.population_signal_recorded@1",
        "mixed",
        (
            (SocialFactAuthority, "record_admitted_population_signal_materialization_proposal"),
            (OrganizationAuthority, "materialize_admitted_population_organization"),
        ),
    ),
)


def _descriptor_ref(family_ref: str) -> str:
    return f"descriptor:{family_ref.replace('_', '-')}"


def _replay_reader_refs(family_ref: str) -> tuple[str, str]:
    slug = family_ref.replace("_", "-").removesuffix("@1")
    return (f"reader:{slug}-checkpoint-tail@1", f"reader:{slug}-full@1")


def test_every_ogs_family_descriptor_has_closed_owner_stream_event_privacy_and_replay_metadata() -> None:
    families = {family_ref for family_ref, *_rest in OGS_FAMILY_CASES}
    descriptors = {
        descriptor.family_ref: descriptor
        for descriptor in GovernedAuthorityContractCatalog.all_descriptors()
        if descriptor.family_ref in families
    }

    assert set(descriptors) == families

    for family_ref, owner_ref, stream_pattern, event_type, privacy_scope, owner_paths in OGS_FAMILY_CASES:
        descriptor = descriptors[family_ref]
        assert descriptor.descriptor_ref == _descriptor_ref(family_ref)
        assert descriptor.owner_ref == owner_ref
        assert descriptor.source_stream_pattern == stream_pattern
        assert descriptor.target_stream_pattern == stream_pattern
        assert descriptor.source_event_types == (event_type,)
        assert descriptor.target_event_types == (event_type,)
        assert descriptor.privacy_scope == privacy_scope
        assert descriptor.receipt_reader_ref == "GameplayEventStore.append_batch"
        assert descriptor.replay_reader_refs == _replay_reader_refs(family_ref)
        assert content_model_for_ogs_family(family_ref) is not None
        for owner_cls, method_name in owner_paths:
            assert callable(getattr(owner_cls, method_name))


@pytest.mark.parametrize("recipe", all_ogs_precompiled_recipes())
def test_ogs_precompiled_recipes_admit_exact_source_owner_event_privacy_and_revision(recipe) -> None:
    admitted = validate_ogs_recipe_source(
        recipe_ref=recipe.recipe_ref,
        source_owner_ref=recipe.source_owner_ref,
        source_event_type=recipe.source_event_type,
        source_privacy_scope=recipe.privacy_scope,
        source_revision=4,
        expected_source_revision=4,
    )

    assert admitted is recipe
    assert admitted.target_family_ref == recipe.target_family_ref
    assert admitted.target_owner_ref != admitted.source_owner_ref


@pytest.mark.parametrize("recipe", all_ogs_precompiled_recipes())
def test_ogs_precompiled_recipes_reject_tampered_source_privacy(recipe) -> None:
    bad_privacy = "authority_only" if recipe.privacy_scope == "project" else "project"

    with pytest.raises(OGSRecipeError, match="ogs_recipe_source_admission_rejected"):
        validate_ogs_recipe_source(
            recipe_ref=recipe.recipe_ref,
            source_owner_ref=recipe.source_owner_ref,
            source_event_type=recipe.source_event_type,
            source_privacy_scope=bad_privacy,
            source_revision=4,
            expected_source_revision=4,
        )


def test_population_signal_materialization_uses_distinct_source_signal_and_target_policy_content_models() -> None:
    source = PopulationSignalContent.model_validate(
        {
            "signal_ref": "signal:riverward-labor-demand@1",
            "region_ref": "region:riverward@1",
            "period_ref": "period:riverward-spring@1",
            "metric_kind": "labor_demand",
            "quantity": 24,
            "source_revision_ref": "population:riverward@4",
            "public_digest": "sha256:" + "a" * 64,
        }
    )
    target = PopulationMaterializationPolicyContent.model_validate(
        {
            "materialization_policy_ref": "policy:riverward-organization-materialization@1",
            "target_subject_kind": "organization",
            "required_signal_kind_refs": (),
            "identity_policy_ref": "policy:riverward-identity@1",
        }
    )

    assert type(source) is PopulationSignalContent
    assert type(target) is PopulationMaterializationPolicyContent
    assert PopulationSignalContent is not PopulationMaterializationPolicyContent
    assert content_model_for_ogs_family("population_signal_materialization@1") is PopulationMaterializationPolicyContent


def test_every_ogs_family_activates_one_immutable_v3_binding() -> None:
    for family_ref, *_rest in OGS_FAMILY_CASES:
        manifest = _manifest(family_ref=family_ref)
        registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
        registry.install(manifest)
        active = registry.activate((manifest.patch_revision_id,))
        assert len(active.capability_bindings) == 1
        binding = active.capability_bindings[0]
        assert binding.family_ref == family_ref
        assert binding.package_revision == manifest.patch_revision_id
        assert binding.content_digest == manifest.content_digest
        assert binding.declaration_digest.startswith("sha256:")
        assert binding.descriptor_revision == binding.descriptor_ref
