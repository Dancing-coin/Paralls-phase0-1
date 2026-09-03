from __future__ import annotations

from app.gameplay.organization_government_social_content import (
    GovernmentPolicyContent,
    OrganizationDefinitionContent,
    OrganizationRoleDelegationContent,
    PopulationMaterializationPolicyContent,
    PopulationSignalContent,
    SocialGroupContent,
    SocialRelationshipContent,
)


def test_ogs_content_matrix_accepts_two_distinct_immutable_contents_per_reusable_shape() -> None:
    definitions = (
        OrganizationDefinitionContent.model_validate({"organization_ref": "organization:one@1", "organization_schema_ref": "schema:organization@1", "jurisdiction_ref": "jurisdiction:a@1", "charter_policy_ref": "policy:charter-a@1", "role_policy_refs": ()}),
        OrganizationDefinitionContent.model_validate({"organization_ref": "organization:two@1", "organization_schema_ref": "schema:organization@1", "jurisdiction_ref": "jurisdiction:b@1", "charter_policy_ref": "policy:charter-b@1", "role_policy_refs": ()}),
    )
    roles = (
        OrganizationRoleDelegationContent.model_validate({"role_ref": "role:one@1", "organization_ref": "organization:one@1", "delegation_policy_ref": "policy:delegation-a@1", "allowed_capability_refs": ()}),
        OrganizationRoleDelegationContent.model_validate({"role_ref": "role:two@1", "organization_ref": "organization:two@1", "delegation_policy_ref": "policy:delegation-b@1", "allowed_capability_refs": ()}),
    )
    policies = (
        GovernmentPolicyContent.model_validate({"policy_ref": "policy:permit-a@1", "jurisdiction_ref": "jurisdiction:a@1", "policy_kind": "permit", "calendar_ref": "calendar:a@1", "activation_mode": "explicit_owner_event", "delegation_evidence_kind_ref": "evidence:delegation@1"}),
        GovernmentPolicyContent.model_validate({"policy_ref": "policy:permit-b@1", "jurisdiction_ref": "jurisdiction:b@1", "policy_kind": "inspection", "calendar_ref": "calendar:b@1", "activation_mode": "explicit_owner_event", "delegation_evidence_kind_ref": "evidence:delegation@1"}),
    )
    relationships = (
        SocialRelationshipContent.model_validate({"relationship_ref": "relationship:one@1", "relationship_kind_ref": "relationship-kind:ally@1", "acceptance_policy_ref": "policy:mutual@1", "required_party_count": 2, "shared_visibility_scope": "project"}),
        SocialRelationshipContent.model_validate({"relationship_ref": "relationship:two@1", "relationship_kind_ref": "relationship-kind:kin@1", "acceptance_policy_ref": "policy:mutual@1", "required_party_count": 2, "shared_visibility_scope": "public"}),
    )
    groups = (
        SocialGroupContent.model_validate({"group_ref": "group:one@1", "group_schema_ref": "schema:group@1", "membership_policy_ref": "policy:membership-a@1", "representative_role_refs": ()}),
        SocialGroupContent.model_validate({"group_ref": "group:two@1", "group_schema_ref": "schema:group@1", "membership_policy_ref": "policy:membership-b@1", "representative_role_refs": ()}),
    )
    signals = (
        PopulationSignalContent.model_validate({"signal_ref": "signal:one@1", "region_ref": "region:a@1", "period_ref": "period:a@1", "metric_kind": "labor_demand", "quantity": 1, "source_revision_ref": "population:a@1", "public_digest": "sha256:" + "a" * 64}),
        PopulationSignalContent.model_validate({"signal_ref": "signal:two@1", "region_ref": "region:b@1", "period_ref": "period:b@1", "metric_kind": "social_pressure", "quantity": 2, "source_revision_ref": "population:b@1", "public_digest": "sha256:" + "b" * 64}),
    )
    materialization = (
        PopulationMaterializationPolicyContent.model_validate({"materialization_policy_ref": "policy:materialize-a@1", "target_subject_kind": "organization", "required_signal_kind_refs": (), "identity_policy_ref": "policy:identity-a@1"}),
        PopulationMaterializationPolicyContent.model_validate({"materialization_policy_ref": "policy:materialize-b@1", "target_subject_kind": "character", "required_signal_kind_refs": (), "identity_policy_ref": "policy:identity-b@1"}),
    )
    assert len({item.organization_ref for item in definitions}) == 2
    assert len({item.role_ref for item in roles}) == 2
    assert len({item.policy_ref for item in policies}) == 2
    assert len({item.relationship_ref for item in relationships}) == 2
    assert len({item.group_ref for item in groups}) == 2
    assert len({item.signal_ref for item in signals}) == 2
    assert len({item.materialization_policy_ref for item in materialization}) == 2
