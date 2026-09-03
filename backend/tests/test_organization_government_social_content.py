from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.organization_government_social_content import (
    GovernmentJurisdictionContent,
    GovernmentPolicyContent,
    OrganizationCharterContent,
    OrganizationDefinitionContent,
    PopulationSignalContent,
    SocialGroupContent,
    SocialRelationshipContent,
)


def test_ogs_typed_content_accepts_versioned_canonical_records() -> None:
    organization = OrganizationDefinitionContent.model_validate(
        {
            "organization_ref": "organization:millers-guild@1",
            "organization_schema_ref": "schema:organization@1",
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "charter_policy_ref": "policy:millers-charter@1",
            "role_policy_refs": ["policy:millers-auditor@1", "policy:millers-steward@1"],
        }
    )
    charter = OrganizationCharterContent.model_validate(
        {
            "charter_ref": "charter:millers-guild@1",
            "organization_ref": "organization:millers-guild@1",
            "governance_policy_ref": "policy:millers-governance@1",
            "membership_policy_ref": "policy:millers-membership@1",
            "delegation_policy_ref": "policy:millers-delegation@1",
            "dissolution_policy_ref": "policy:millers-dissolution@1",
        }
    )
    jurisdiction = GovernmentJurisdictionContent.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
                "jurisdiction_schema_ref": "schema:government-jurisdiction@1",
                "calendar_ref": "calendar:riverward@1",
                "currency_ref": "currency:riverward-mark@1",
            }
        )
    policy = GovernmentPolicyContent.model_validate(
        {
            "policy_ref": "policy:riverward-milling@1",
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "policy_kind": "permit",
            "calendar_ref": "calendar:riverward@1",
            "activation_mode": "explicit_owner_event",
            "delegation_evidence_kind_ref": "evidence:government-delegation@1",
        }
    )
    relationship = SocialRelationshipContent.model_validate(
        {
            "relationship_ref": "relationship:ada-bryn:colleague@1",
            "relationship_kind_ref": "relationship-kind:colleague@1",
            "acceptance_policy_ref": "policy:relationship-mutual@1",
            "required_party_count": 2,
            "shared_visibility_scope": "project",
        }
    )
    group = SocialGroupContent.model_validate(
        {
            "group_ref": "group:riverward-millers@1",
            "group_schema_ref": "schema:social-group@1",
            "membership_policy_ref": "policy:millers-membership@1",
            "representative_role_refs": ["role:chair@1", "role:steward@1"],
        }
    )
    signal = PopulationSignalContent.model_validate(
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

    assert organization.role_policy_refs == (
        "policy:millers-auditor@1",
        "policy:millers-steward@1",
    )
    assert charter.organization_ref == organization.organization_ref
    assert jurisdiction.currency_ref == "currency:riverward-mark@1"
    assert policy.activation_mode == "explicit_owner_event"
    assert relationship.required_party_count == 2
    assert group.representative_role_refs == ("role:chair@1", "role:steward@1")
    assert signal.quantity == 24


def test_ogs_content_rejects_authority_coordinates_and_noncanonical_arrays() -> None:
    with pytest.raises(ValidationError, match="platform_authority_shaped_payload"):
        OrganizationDefinitionContent.model_validate(
            {
                "organization_ref": "organization:millers-guild@1",
                "organization_schema_ref": "schema:organization@1",
                "jurisdiction_ref": "jurisdiction:riverward@1",
                "charter_policy_ref": "policy:millers-charter@1",
                "role_policy_refs": [],
                "owner_ref": "authority:forged",
            }
        )

    with pytest.raises(ValidationError, match="ogs_array_not_canonical"):
        SocialGroupContent.model_validate(
            {
                "group_ref": "group:riverward-millers@1",
                "group_schema_ref": "schema:social-group@1",
                "membership_policy_ref": "policy:millers-membership@1",
                "representative_role_refs": ["role:steward@1", "role:chair@1"],
            }
        )


def test_ogs_content_requires_versioned_refs_strict_numbers_and_public_signal_only() -> None:
    with pytest.raises(ValidationError, match="ogs_reference_invalid"):
        GovernmentPolicyContent.model_validate(
            {
                "policy_ref": "policy:riverward-milling",
                "jurisdiction_ref": "jurisdiction:riverward@1",
                "policy_kind": "permit",
                "calendar_ref": "calendar:riverward@1",
                "activation_mode": "explicit_owner_event",
                "delegation_evidence_kind_ref": "evidence:government-delegation@1",
            }
        )

    with pytest.raises(ValidationError):
        SocialRelationshipContent.model_validate(
            {
                "relationship_ref": "relationship:ada-bryn:colleague@1",
                "relationship_kind_ref": "relationship-kind:colleague@1",
                "acceptance_policy_ref": "policy:relationship-mutual@1",
                "required_party_count": True,
            }
        )

    with pytest.raises(ValidationError, match="ogs_population_signal_digest_invalid"):
        PopulationSignalContent.model_validate(
            {
                "signal_ref": "signal:riverward-labor-demand@1",
                "region_ref": "region:riverward@1",
                "period_ref": "period:riverward-spring@1",
                "metric_kind": "labor_demand",
                "quantity": 24,
                "source_revision_ref": "population:riverward@4",
                "public_digest": "not-a-digest",
            }
        )
