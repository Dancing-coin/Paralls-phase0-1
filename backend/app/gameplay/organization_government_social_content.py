"""Strict immutable v3/platform-2.0 content for the social-institution platform.

The models in this module intentionally describe package content only.  Owner
coordinates, event coordinates, receipts, and settlement fragments remain in
immutable descriptors and cannot be authored by a package caller.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel
from app.gameplay.patch_runtime import _require_author_canonical, _validate_platform_content


NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
BasisPoints = Annotated[int, Field(strict=True, ge=0, le=10_000)]


def _versioned(value: str, prefix: str) -> str:
    if not value.startswith(prefix) or "@" not in value or value.endswith("@"):
        raise ValueError("ogs_reference_invalid")
    return value


def _canonical(values: tuple[str, ...]) -> None:
    try:
        _require_author_canonical(values, identity=lambda value: value)
    except ValueError as exc:
        raise ValueError("ogs_array_not_canonical") from exc
    if values != tuple(sorted(values)):
        raise ValueError("ogs_array_not_canonical")


class OGSContentModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def reject_authority_shaped_payload(cls, value: object) -> object:
        if isinstance(value, cls):
            return value
        _validate_platform_content(value)
        return value


class OrganizationDefinitionContent(OGSContentModel):
    organization_ref: str = Field(min_length=1)
    organization_schema_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    charter_policy_ref: str = Field(min_length=1)
    role_policy_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_content(self) -> "OrganizationDefinitionContent":
        _versioned(self.organization_ref, "organization:")
        _versioned(self.organization_schema_ref, "schema:")
        _versioned(self.jurisdiction_ref, "jurisdiction:")
        _versioned(self.charter_policy_ref, "policy:")
        for ref in self.role_policy_refs:
            _versioned(ref, "policy:")
        _canonical(self.role_policy_refs)
        return self


class OrganizationCharterContent(OGSContentModel):
    charter_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    governance_policy_ref: str = Field(min_length=1)
    membership_policy_ref: str = Field(min_length=1)
    delegation_policy_ref: str = Field(min_length=1)
    dissolution_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "OrganizationCharterContent":
        _versioned(self.charter_ref, "charter:")
        _versioned(self.organization_ref, "organization:")
        for ref in (
            self.governance_policy_ref,
            self.membership_policy_ref,
            self.delegation_policy_ref,
            self.dissolution_policy_ref,
        ):
            _versioned(ref, "policy:")
        return self


class OrganizationRoleDelegationContent(OGSContentModel):
    role_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    delegation_policy_ref: str = Field(min_length=1)
    allowed_capability_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_content(self) -> "OrganizationRoleDelegationContent":
        _versioned(self.role_ref, "role:")
        _versioned(self.organization_ref, "organization:")
        _versioned(self.delegation_policy_ref, "policy:")
        for ref in self.allowed_capability_refs:
            _versioned(ref, "capability:")
        _canonical(self.allowed_capability_refs)
        return self


class OrganizationOperatingPeriodContent(OGSContentModel):
    operating_period_policy_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    calendar_ref: str = Field(min_length=1)
    minimum_window_ticks: PositiveInt
    contribution_evidence_kind_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_content(self) -> "OrganizationOperatingPeriodContent":
        _versioned(self.operating_period_policy_ref, "policy:")
        _versioned(self.organization_ref, "organization:")
        _versioned(self.calendar_ref, "calendar:")
        for ref in self.contribution_evidence_kind_refs:
            _versioned(ref, "evidence:")
        _canonical(self.contribution_evidence_kind_refs)
        return self


class OrganizationCommitmentPolicyContent(OGSContentModel):
    commitment_policy_ref: str = Field(min_length=1)
    organization_ref: str = Field(min_length=1)
    budget_policy_ref: str = Field(min_length=1)
    allowed_commitment_kind_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_content(self) -> "OrganizationCommitmentPolicyContent":
        _versioned(self.commitment_policy_ref, "policy:")
        _versioned(self.organization_ref, "organization:")
        _versioned(self.budget_policy_ref, "policy:")
        for ref in self.allowed_commitment_kind_refs:
            _versioned(ref, "commitment-kind:")
        _canonical(self.allowed_commitment_kind_refs)
        return self


class GovernmentJurisdictionContent(OGSContentModel):
    jurisdiction_ref: str = Field(min_length=1)
    jurisdiction_schema_ref: str = Field(min_length=1)
    calendar_ref: str = Field(min_length=1)
    currency_ref: str = Field(min_length=1)
    parent_jurisdiction_ref: str | None = None

    @model_validator(mode="after")
    def validate_content(self) -> "GovernmentJurisdictionContent":
        _versioned(self.jurisdiction_ref, "jurisdiction:")
        _versioned(self.jurisdiction_schema_ref, "schema:")
        _versioned(self.calendar_ref, "calendar:")
        _versioned(self.currency_ref, "currency:")
        if self.parent_jurisdiction_ref is not None:
            _versioned(self.parent_jurisdiction_ref, "jurisdiction:")
            if self.parent_jurisdiction_ref == self.jurisdiction_ref:
                raise ValueError("ogs_jurisdiction_self_parent")
        return self


class GovernmentPolicyContent(OGSContentModel):
    policy_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    policy_kind: Literal["permit", "tax", "inspection", "public_project", "notice", "enforcement"]
    calendar_ref: str = Field(min_length=1)
    activation_mode: Literal["explicit_owner_event"]
    delegation_evidence_kind_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "GovernmentPolicyContent":
        _versioned(self.policy_ref, "policy:")
        _versioned(self.jurisdiction_ref, "jurisdiction:")
        _versioned(self.calendar_ref, "calendar:")
        _versioned(self.delegation_evidence_kind_ref, "evidence:")
        return self


class GovernmentPermitInspectionContent(OGSContentModel):
    permit_policy_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    activity_kind_refs: tuple[str, ...] = ()
    inspection_policy_ref: str = Field(min_length=1)
    appeal_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "GovernmentPermitInspectionContent":
        for ref in (self.permit_policy_ref, self.inspection_policy_ref, self.appeal_policy_ref):
            _versioned(ref, "policy:")
        _versioned(self.jurisdiction_ref, "jurisdiction:")
        for ref in self.activity_kind_refs:
            _versioned(ref, "activity-kind:")
        _canonical(self.activity_kind_refs)
        return self


class GovernmentTaxTreasuryContent(OGSContentModel):
    tax_policy_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    currency_ref: str = Field(min_length=1)
    tax_kind_ref: str = Field(min_length=1)
    rate_basis_points: BasisPoints
    treasury_budget_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "GovernmentTaxTreasuryContent":
        for ref in (self.tax_policy_ref, self.treasury_budget_policy_ref):
            _versioned(ref, "policy:")
        _versioned(self.jurisdiction_ref, "jurisdiction:")
        _versioned(self.currency_ref, "currency:")
        _versioned(self.tax_kind_ref, "tax-kind:")
        return self


class GovernmentPublicProjectContent(OGSContentModel):
    public_project_policy_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    project_kind_ref: str = Field(min_length=1)
    audit_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "GovernmentPublicProjectContent":
        _versioned(self.public_project_policy_ref, "policy:")
        _versioned(self.jurisdiction_ref, "jurisdiction:")
        _versioned(self.project_kind_ref, "project-kind:")
        _versioned(self.audit_policy_ref, "policy:")
        return self


class SocialIdentityContent(OGSContentModel):
    identity_schema_ref: str = Field(min_length=1)
    subject_kind: Literal["character", "government", "organization"]
    identity_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "SocialIdentityContent":
        _versioned(self.identity_schema_ref, "schema:")
        _versioned(self.identity_policy_ref, "policy:")
        return self


class SocialRelationshipContent(OGSContentModel):
    relationship_ref: str = Field(min_length=1)
    relationship_kind_ref: str = Field(min_length=1)
    acceptance_policy_ref: str = Field(min_length=1)
    required_party_count: PositiveInt
    shared_visibility_scope: Literal["project", "public"]

    @model_validator(mode="after")
    def validate_content(self) -> "SocialRelationshipContent":
        _versioned(self.relationship_ref, "relationship:")
        _versioned(self.relationship_kind_ref, "relationship-kind:")
        _versioned(self.acceptance_policy_ref, "policy:")
        if self.required_party_count < 2:
            raise ValueError("ogs_relationship_party_count_invalid")
        return self


class SocialReputationPolicyContent(OGSContentModel):
    reputation_policy_ref: str = Field(min_length=1)
    reputation_kind_ref: str = Field(min_length=1)
    evidence_kind_refs: tuple[str, ...] = ()
    minimum_confidence_basis_points: BasisPoints

    @model_validator(mode="after")
    def validate_content(self) -> "SocialReputationPolicyContent":
        _versioned(self.reputation_policy_ref, "policy:")
        _versioned(self.reputation_kind_ref, "reputation-kind:")
        for ref in self.evidence_kind_refs:
            _versioned(ref, "evidence:")
        _canonical(self.evidence_kind_refs)
        return self


class SocialHouseholdContent(OGSContentModel):
    household_ref: str = Field(min_length=1)
    household_schema_ref: str = Field(min_length=1)
    membership_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "SocialHouseholdContent":
        _versioned(self.household_ref, "household:")
        _versioned(self.household_schema_ref, "schema:")
        _versioned(self.membership_policy_ref, "policy:")
        return self


class SocialGroupContent(OGSContentModel):
    group_ref: str = Field(min_length=1)
    group_schema_ref: str = Field(min_length=1)
    membership_policy_ref: str = Field(min_length=1)
    representative_role_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_content(self) -> "SocialGroupContent":
        _versioned(self.group_ref, "group:")
        _versioned(self.group_schema_ref, "schema:")
        _versioned(self.membership_policy_ref, "policy:")
        for ref in self.representative_role_refs:
            _versioned(ref, "role:")
        _canonical(self.representative_role_refs)
        return self


class SocialNormConflictContent(OGSContentModel):
    norm_policy_ref: str = Field(min_length=1)
    conflict_kind_ref: str = Field(min_length=1)
    mediation_policy_ref: str = Field(min_length=1)
    appeal_policy_ref: str = Field(min_length=1)
    allowed_resolution_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_content(self) -> "SocialNormConflictContent":
        for ref in (self.norm_policy_ref, self.mediation_policy_ref, self.appeal_policy_ref):
            _versioned(ref, "policy:")
        _versioned(self.conflict_kind_ref, "conflict-kind:")
        for ref in self.allowed_resolution_refs:
            _versioned(ref, "resolution:")
        _canonical(self.allowed_resolution_refs)
        return self


class PopulationSignalContent(OGSContentModel):
    signal_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    metric_kind: Literal["labor_demand", "labor_supply", "housing_pressure", "social_pressure"]
    quantity: NonNegativeInt
    source_revision_ref: str = Field(min_length=1)
    public_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "PopulationSignalContent":
        _versioned(self.signal_ref, "signal:")
        _versioned(self.region_ref, "region:")
        _versioned(self.period_ref, "period:")
        _versioned(self.source_revision_ref, "population:")
        if not self.public_digest.startswith("sha256:") or len(self.public_digest) != 71:
            raise ValueError("ogs_population_signal_digest_invalid")
        return self


class PopulationMaterializationPolicyContent(OGSContentModel):
    materialization_policy_ref: str = Field(min_length=1)
    target_subject_kind: Literal["character", "organization"]
    required_signal_kind_refs: tuple[str, ...] = ()
    identity_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_content(self) -> "PopulationMaterializationPolicyContent":
        _versioned(self.materialization_policy_ref, "policy:")
        _versioned(self.identity_policy_ref, "policy:")
        for ref in self.required_signal_kind_refs:
            _versioned(ref, "signal-kind:")
        _canonical(self.required_signal_kind_refs)
        return self


_FAMILY_CONTENT_MODELS: dict[str, type[OGSContentModel]] = {
    "organization_lifecycle@1": OrganizationDefinitionContent,
    "organization_membership_delegation@1": OrganizationRoleDelegationContent,
    "organization_operating_period@1": OrganizationOperatingPeriodContent,
    "organization_commitment_budget@1": OrganizationCommitmentPolicyContent,
    "government_jurisdiction_policy@1": GovernmentPolicyContent,
    "government_permit_inspection_enforcement@1": GovernmentPermitInspectionContent,
    "government_tax_treasury_project@1": GovernmentTaxTreasuryContent,
    "government_notice_audit@1": GovernmentPublicProjectContent,
    "social_identity_relationship@1": SocialRelationshipContent,
    "social_household_group@1": SocialGroupContent,
    "social_norm_conflict@1": SocialNormConflictContent,
    "social_private_projection@1": SocialIdentityContent,
    "population_signal_materialization@1": PopulationMaterializationPolicyContent,
}


def content_model_for_ogs_family(family_ref: str) -> type[OGSContentModel]:
    try:
        return _FAMILY_CONTENT_MODELS[family_ref]
    except KeyError as exc:
        raise KeyError("ogs_family_content_model_unknown") from exc


__all__ = [
    "GovernmentJurisdictionContent",
    "GovernmentPermitInspectionContent",
    "GovernmentPolicyContent",
    "GovernmentPublicProjectContent",
    "GovernmentTaxTreasuryContent",
    "OGSContentModel",
    "OrganizationCharterContent",
    "OrganizationCommitmentPolicyContent",
    "OrganizationDefinitionContent",
    "OrganizationOperatingPeriodContent",
    "OrganizationRoleDelegationContent",
    "PopulationMaterializationPolicyContent",
    "PopulationSignalContent",
    "SocialGroupContent",
    "SocialHouseholdContent",
    "SocialIdentityContent",
    "SocialNormConflictContent",
    "SocialRelationshipContent",
    "SocialReputationPolicyContent",
    "content_model_for_ogs_family",
]
