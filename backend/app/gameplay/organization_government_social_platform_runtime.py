"""Read-only replay contracts for the federated Organization/Government/Social platform.

This is deliberately a projector and strict intent vocabulary, not a new
authority or writer. Existing OrganizationAuthority, GovernmentAuthority and
SocialFactAuthority remain the only owners allowed to append their fragments.
"""
from __future__ import annotations

from hashlib import sha256
import json
from types import MappingProxyType
from typing import Literal, Mapping, Sequence

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import GameplayEvent, StrictGameplayModel


OGS_ORGANIZATION_PRINCIPAL_REF = "actor_gameplay.organization_domain"
OGS_GOVERNMENT_PRINCIPAL_REF = "actor_gameplay.government_domain"
OGS_SOCIAL_PRINCIPAL_REF = "authority:p5:social"
OGS_PUBLIC_VISIBILITY_POLICY = "public"
OGS_POPULATION_SIGNAL_EVENT_TYPE = "gameplay.social.population_signal_recorded@1"

ORGANIZATION_LIFECYCLE_STREAM_GRAMMAR = "gameplay:organization:{organization_ref}"
ORGANIZATION_MEMBERSHIP_STREAM_GRAMMAR = ORGANIZATION_LIFECYCLE_STREAM_GRAMMAR
ORGANIZATION_OPERATING_PERIOD_STREAM_GRAMMAR = ORGANIZATION_LIFECYCLE_STREAM_GRAMMAR
ORGANIZATION_COMMITMENT_STREAM_GRAMMAR = ORGANIZATION_LIFECYCLE_STREAM_GRAMMAR
GOVERNMENT_JURISDICTION_STREAM_GRAMMAR = "gameplay:government:{jurisdiction_ref}"
GOVERNMENT_CASE_STREAM_GRAMMAR = "gameplay:government:case:{case_ref}"
GOVERNMENT_TAX_TREASURY_STREAM_GRAMMAR = GOVERNMENT_JURISDICTION_STREAM_GRAMMAR
GOVERNMENT_NOTICE_STREAM_GRAMMAR = GOVERNMENT_JURISDICTION_STREAM_GRAMMAR
OGS_POPULATION_SIGNAL_STREAM_GRAMMAR = "gameplay:social:population:{signal_ref}"
OGS_STREAM_GRAMMAR_PREFIXES = ("gameplay:organization:", "gameplay:government:", "gameplay:social:")


class OGSPlatformRuntimeError(ValueError):
    pass


class _OGSModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class _Intent(_OGSModel):
    provenance_ref: str = Field(pattern=r"^provenance:.*@.+$", min_length=1)
    source_revision_pin: int = Field(strict=True, ge=0)
    package_pin: str | None = Field(default=None, pattern=r"^package:.*@.+$")
    content_digest_pin: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    declaration_digest_pin: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    descriptor_pin: str | None = Field(default=None, pattern=r"^descriptor:.*@.+$")
    active_set_digest_pin: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    policy_revision_pin: str | None = Field(default=None, pattern=r"^policy:.*@.+$")
    package_revision_pin: str | None = Field(default=None, pattern=r"^package:.*@.+$")
    declaration_ref_pin: str | None = Field(default=None, pattern=r"^declaration:.*@.+$")
    descriptor_revision_pin: str | None = Field(default=None, pattern=r"^descriptor:.*@.+$")


class _Record(_Intent):
    revision: int = Field(strict=True, ge=1)


class OrganizationLifecycleIntent(_Intent):
    organization_ref: str = Field(pattern=r"^organization:.*@.+$")
    from_state: Literal["draft", "registered", "active", "suspended", "dissolving", "dissolved"]
    to_state: Literal["registered", "active", "suspended", "dissolving", "dissolved"]
    materialization_source_event_id: str | None = Field(default=None, pattern=r"^event:")
    materialization_source_stream_revision: int | None = Field(default=None, strict=True, ge=1)

    @model_validator(mode="after")
    def legal_transition(self) -> "OrganizationLifecycleIntent":
        legal = {
            "draft": {"registered", "active"}, "registered": {"active", "suspended", "dissolving"},
            "active": {"suspended", "dissolving"}, "suspended": {"active", "dissolving"},
            "dissolving": {"dissolved"}, "dissolved": set(),
        }
        if self.to_state not in legal[self.from_state]:
            raise ValueError("ogs_organization_lifecycle_transition_invalid")
        if (self.materialization_source_event_id is None) != (
            self.materialization_source_stream_revision is None
        ):
            raise ValueError("ogs_organization_materialization_provenance_invalid")
        if self.materialization_source_event_id is not None and (
            self.from_state != "draft" or self.to_state != "registered"
        ):
            raise ValueError("ogs_organization_materialization_transition_invalid")
        return self


class OrganizationLifecycleRecord(OrganizationLifecycleIntent, _Record):
    pass


class OrganizationMembershipDelegationIntent(_Intent):
    organization_ref: str = Field(pattern=r"^organization:.*@.+$")
    member_ref: str = Field(pattern=r"^(character|organization):")
    role_ref: str = Field(pattern=r"^role:.*@.+$")
    delegation_state: Literal["proposed", "delegated", "active", "suspended", "revoked"]


class OrganizationMembershipDelegationRecord(OrganizationMembershipDelegationIntent, _Record):
    pass


class OrganizationOperatingPeriodIntent(_Intent):
    organization_ref: str = Field(pattern=r"^organization:.*@.+$")
    period_ref: str = Field(pattern=r"^period:.*@.+$")
    period_state: Literal["planned", "open", "closed", "cancelled"]
    opens_at_tick: int = Field(strict=True, ge=0)
    closes_at_tick: int = Field(strict=True, ge=0)

    @model_validator(mode="after")
    def valid_window(self) -> "OrganizationOperatingPeriodIntent":
        if self.closes_at_tick < self.opens_at_tick:
            raise ValueError("ogs_operating_period_window_invalid")
        return self


class OrganizationOperatingPeriodRecord(OrganizationOperatingPeriodIntent, _Record):
    pass


class OrganizationCommitmentBudgetIntent(_Intent):
    organization_ref: str = Field(pattern=r"^organization:.*@.+$")
    budget_ref: str = Field(pattern=r"^budget:.*@.+$")
    budget_state: Literal["proposed", "eligible", "consumed", "closed"]
    amount_minor: int = Field(strict=True, ge=0)


class OrganizationCommitmentBudgetRecord(OrganizationCommitmentBudgetIntent, _Record):
    pass


class GovernmentPolicyLifecycleIntent(_Intent):
    jurisdiction_ref: str = Field(pattern=r"^jurisdiction:.*@.+$")
    policy_ref: str = Field(pattern=r"^policy:.*@.+$")
    policy_state: Literal["draft", "published", "active", "superseded", "revoked"]


class GovernmentPolicyLifecycleRecord(GovernmentPolicyLifecycleIntent, _Record):
    pass


class GovernmentPermitInspectionCaseIntent(_Intent):
    jurisdiction_ref: str = Field(pattern=r"^jurisdiction:.*@.+$")
    case_ref: str = Field(pattern=r"^case:.*@.+$")
    case_state: Literal["opened", "adjudicated", "appealed", "final"]


class GovernmentPermitInspectionCaseRecord(GovernmentPermitInspectionCaseIntent, _Record):
    pass


class GovernmentTaxTreasuryProjectIntent(_Intent):
    jurisdiction_ref: str = Field(pattern=r"^jurisdiction:.*@.+$")
    project_ref: str = Field(pattern=r"^project:.*@.+$")
    project_state: Literal["proposed", "eligible", "audited", "closed"]
    amount_minor: int = Field(strict=True, ge=0)


class GovernmentTaxTreasuryProjectRecord(GovernmentTaxTreasuryProjectIntent, _Record):
    pass


class GovernmentNoticeAuditIntent(_Intent):
    jurisdiction_ref: str = Field(pattern=r"^jurisdiction:.*@.+$")
    notice_ref: str = Field(pattern=r"^notice:.*@.+$")
    notice_state: Literal["drafted", "issued", "acknowledged", "disputed", "resolved", "archived"]
    visibility_scope: Literal["public", "project", "authority_only"]


class GovernmentNoticeAuditRecord(GovernmentNoticeAuditIntent, _Record):
    pass


def _two_or_more(values: tuple[str, ...], error: str) -> tuple[str, ...]:
    if len(values) < 2 or len(values) != len(set(values)) or tuple(sorted(values)) != values:
        raise ValueError(error)
    return values


class SocialIdentityRelationshipIntent(_Intent):
    relationship_ref: str = Field(pattern=r"^relationship:.*@.+$")
    participant_refs: tuple[str, ...]
    relationship_state: Literal["proposed", "active", "suspended", "ended"]

    @model_validator(mode="after")
    def accepted_parties(self) -> "SocialIdentityRelationshipIntent":
        _two_or_more(self.participant_refs, "ogs_relationship_participants_invalid")
        return self


class SocialIdentityRelationshipRecord(SocialIdentityRelationshipIntent, _Record):
    pass


class SocialHouseholdGroupIntent(_Intent):
    group_ref: str = Field(pattern=r"^(group|household):.*@.+$")
    member_refs: tuple[str, ...]
    group_state: Literal["forming", "active", "dissolving", "dissolved"]

    @model_validator(mode="after")
    def members(self) -> "SocialHouseholdGroupIntent":
        _two_or_more(self.member_refs, "ogs_group_members_invalid")
        return self


class SocialHouseholdGroupRecord(SocialHouseholdGroupIntent, _Record):
    pass


class SocialNormConflictIntent(_Intent):
    case_ref: str = Field(pattern=r"^case:.*@.+$")
    subject_refs: tuple[str, ...]
    conflict_state: Literal["opened", "mediated", "adjudicated", "appealed", "final"]

    @model_validator(mode="after")
    def subjects(self) -> "SocialNormConflictIntent":
        _two_or_more(self.subject_refs, "ogs_conflict_subjects_invalid")
        return self


class SocialNormConflictRecord(SocialNormConflictIntent, _Record):
    pass


class SocialPrivateProjectionIntent(_Intent):
    participant_ref: str = Field(pattern=r"^character:")
    projection_state: Literal["admitted", "redacted", "revoked"]
    visibility_scope: Literal["actor_private"]


class SocialPrivateProjectionRecord(SocialPrivateProjectionIntent, _Record):
    pass


class PopulationSignalMaterializationProposalIntent(_Intent):
    signal_ref: str = Field(pattern=r"^signal:.*@.+$")
    materialization_state: Literal["proposed", "admitted", "identity_allocated", "target_owner_created", "rejected"]
    visibility_scope: Literal["public"]
    allocated_subject_ref: str | None = Field(default=None, pattern=r"^(character|organization):.*@.+$")

    @model_validator(mode="after")
    def materialization_subject(self) -> "PopulationSignalMaterializationProposalIntent":
        if self.materialization_state == "identity_allocated" and self.allocated_subject_ref is None:
            raise ValueError("ogs_population_identity_subject_missing")
        if self.materialization_state != "identity_allocated" and self.allocated_subject_ref is not None:
            raise ValueError("ogs_population_identity_subject_unexpected")
        return self


class PopulationSignalMaterializationProposalRecord(PopulationSignalMaterializationProposalIntent, _Record):
    pass


class OGSPlatformProjection(_OGSModel):
    organization_lifecycles: Mapping[str, str] = Field(default_factory=dict)
    organization_memberships: Mapping[str, OrganizationMembershipDelegationRecord] = Field(default_factory=dict)
    organization_operating_periods: Mapping[str, OrganizationOperatingPeriodRecord] = Field(default_factory=dict)
    organization_commitments: Mapping[str, OrganizationCommitmentBudgetRecord] = Field(default_factory=dict)
    government_policies: Mapping[str, GovernmentPolicyLifecycleRecord] = Field(default_factory=dict)
    government_cases: Mapping[str, GovernmentPermitInspectionCaseRecord] = Field(default_factory=dict)
    government_tax_projects: Mapping[str, GovernmentTaxTreasuryProjectRecord] = Field(default_factory=dict)
    government_notices: Mapping[str, GovernmentNoticeAuditRecord] = Field(default_factory=dict)
    social_relationships: Mapping[str, SocialIdentityRelationshipRecord] = Field(default_factory=dict)
    social_groups: Mapping[str, SocialHouseholdGroupRecord] = Field(default_factory=dict)
    social_conflicts: Mapping[str, SocialNormConflictRecord] = Field(default_factory=dict)
    social_private_projections: Mapping[str, SocialPrivateProjectionRecord] = Field(default_factory=dict)
    population_signals: Mapping[str, PopulationSignalMaterializationProposalRecord] = Field(default_factory=dict)
    source_revision_vector: Mapping[str, int] = Field(default_factory=dict)
    projection_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


_EVENT_MODELS: Mapping[str, tuple[type[_Intent], str, Literal["project", "public", "mixed", "actor_private"]]] = {
    "gameplay.organization.lifecycle_transitioned@1": (OrganizationLifecycleIntent, "organization", "project"),
    "gameplay.organization.membership_delegation_recorded@1": (OrganizationMembershipDelegationIntent, "organization", "project"),
    "gameplay.organization.operating_period_recorded@1": (OrganizationOperatingPeriodIntent, "organization", "project"),
    "gameplay.organization.commitment_budget_proposed@1": (OrganizationCommitmentBudgetIntent, "organization", "project"),
    "gameplay.government.policy_lifecycle_recorded@1": (GovernmentPolicyLifecycleIntent, "government", "project"),
    "gameplay.government.permit_inspection_case_recorded@1": (GovernmentPermitInspectionCaseIntent, "government_case", "project"),
    "gameplay.government.tax_treasury_project_proposed@1": (GovernmentTaxTreasuryProjectIntent, "government", "authority_only"),
    "gameplay.government.notice_audit_recorded@1": (GovernmentNoticeAuditIntent, "government", "mixed"),
    "gameplay.social.identity_relationship_recorded@1": (SocialIdentityRelationshipIntent, "social_relationship", "mixed"),
    "gameplay.social.household_group_recorded@1": (SocialHouseholdGroupIntent, "social_group", "project"),
    "gameplay.social.norm_conflict_recorded@1": (SocialNormConflictIntent, "social_case", "mixed"),
    "gameplay.social.private_projection_recorded@1": (SocialPrivateProjectionIntent, "social_private", "actor_private"),
    OGS_POPULATION_SIGNAL_EVENT_TYPE: (PopulationSignalMaterializationProposalIntent, "population", "public"),
}

_ACTIVATION_PIN_FIELDS = (
    "package_revision_pin",
    "content_digest_pin",
    "declaration_ref_pin",
    "declaration_digest_pin",
    "descriptor_pin",
    "descriptor_revision_pin",
    "active_set_digest_pin",
)


class OrganizationGovernmentSocialProjector:
    """Replays only fixed OGS events and rejects forged stream/privacy coordinates."""

    def rebuild(
        self, events: Sequence[GameplayEvent], *, checkpoint: OGSPlatformProjection | None = None
    ) -> OGSPlatformProjection:
        if checkpoint is not None:
            self._verify_checkpoint(checkpoint)
        lifecycle = dict(checkpoint.organization_lifecycles) if checkpoint else {}
        memberships = dict(checkpoint.organization_memberships) if checkpoint else {}
        periods = dict(checkpoint.organization_operating_periods) if checkpoint else {}
        commitments = dict(checkpoint.organization_commitments) if checkpoint else {}
        policies = dict(checkpoint.government_policies) if checkpoint else {}
        cases = dict(checkpoint.government_cases) if checkpoint else {}
        tax_projects = dict(checkpoint.government_tax_projects) if checkpoint else {}
        notices = dict(checkpoint.government_notices) if checkpoint else {}
        relationships = dict(checkpoint.social_relationships) if checkpoint else {}
        groups = dict(checkpoint.social_groups) if checkpoint else {}
        conflicts = dict(checkpoint.social_conflicts) if checkpoint else {}
        private_projections = dict(checkpoint.social_private_projections) if checkpoint else {}
        signals = dict(checkpoint.population_signals) if checkpoint else {}
        revisions = dict(checkpoint.source_revision_vector) if checkpoint else {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            details = _EVENT_MODELS.get(event.event_type)
            if details is None:
                continue
            model, stream_kind, privacy = details
            self._validate_event(event, model, stream_kind, privacy)
            payload = model.model_validate(event.payload)
            revisions[event.stream_id] = max(revisions.get(event.stream_id, 0), event.stream_revision)
            if isinstance(payload, OrganizationLifecycleIntent):
                prior = lifecycle.get(payload.organization_ref, "draft")
                if prior != payload.from_state:
                    raise OGSPlatformRuntimeError("ogs_organization_lifecycle_replay_invalid")
                lifecycle[payload.organization_ref] = payload.to_state
            if isinstance(payload, PopulationSignalMaterializationProposalIntent):
                if payload.signal_ref in signals:
                    raise OGSPlatformRuntimeError("ogs_population_signal_duplicate")
                signals[payload.signal_ref] = PopulationSignalMaterializationProposalRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, SocialIdentityRelationshipIntent):
                if payload.relationship_ref in relationships:
                    raise OGSPlatformRuntimeError("ogs_social_relationship_duplicate")
                relationships[payload.relationship_ref] = SocialIdentityRelationshipRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, GovernmentPolicyLifecycleIntent):
                existing = policies.get(payload.policy_ref)
                if existing is not None and payload.policy_state in {"draft", "published", "active"}:
                    raise OGSPlatformRuntimeError("ogs_government_policy_duplicate")
                policies[payload.policy_ref] = GovernmentPolicyLifecycleRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, OrganizationMembershipDelegationIntent):
                membership_ref = f"{payload.organization_ref}|{payload.member_ref}"
                memberships[membership_ref] = OrganizationMembershipDelegationRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, OrganizationOperatingPeriodIntent):
                period_key = f"{payload.organization_ref}|{payload.period_ref}"
                periods[period_key] = OrganizationOperatingPeriodRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, OrganizationCommitmentBudgetIntent):
                commitments[payload.budget_ref] = OrganizationCommitmentBudgetRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, GovernmentPermitInspectionCaseIntent):
                cases[payload.case_ref] = GovernmentPermitInspectionCaseRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, GovernmentTaxTreasuryProjectIntent):
                tax_projects[payload.project_ref] = GovernmentTaxTreasuryProjectRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, GovernmentNoticeAuditIntent):
                notices[payload.notice_ref] = GovernmentNoticeAuditRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, SocialHouseholdGroupIntent):
                groups[payload.group_ref] = SocialHouseholdGroupRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, SocialNormConflictIntent):
                conflicts[payload.case_ref] = SocialNormConflictRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
            if isinstance(payload, SocialPrivateProjectionIntent):
                private_projections[payload.participant_ref] = SocialPrivateProjectionRecord.model_validate(
                    {**payload.model_dump(mode="json"), "revision": event.stream_revision}
                )
        state = {
            "organization_lifecycles": dict(sorted(lifecycle.items())),
            "organization_memberships": {key: value.model_dump(mode="json") for key, value in sorted(memberships.items())},
            "organization_operating_periods": {key: value.model_dump(mode="json") for key, value in sorted(periods.items())},
            "organization_commitments": {key: value.model_dump(mode="json") for key, value in sorted(commitments.items())},
            "government_policies": {key: value.model_dump(mode="json") for key, value in sorted(policies.items())},
            "government_cases": {key: value.model_dump(mode="json") for key, value in sorted(cases.items())},
            "government_tax_projects": {key: value.model_dump(mode="json") for key, value in sorted(tax_projects.items())},
            "government_notices": {key: value.model_dump(mode="json") for key, value in sorted(notices.items())},
            "social_relationships": {key: value.model_dump(mode="json") for key, value in sorted(relationships.items())},
            "social_groups": {key: value.model_dump(mode="json") for key, value in sorted(groups.items())},
            "social_conflicts": {key: value.model_dump(mode="json") for key, value in sorted(conflicts.items())},
            "social_private_projections": {key: value.model_dump(mode="json") for key, value in sorted(private_projections.items())},
            "population_signals": {
                key: value.model_dump(mode="json") for key, value in sorted(signals.items())
            },
            "source_revision_vector": dict(sorted(revisions.items())),
        }
        digest = "sha256:" + sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        return OGSPlatformProjection(
            organization_lifecycles=MappingProxyType(dict(sorted(lifecycle.items()))),
            organization_memberships=MappingProxyType(dict(sorted(memberships.items()))),
            organization_operating_periods=MappingProxyType(dict(sorted(periods.items()))),
            organization_commitments=MappingProxyType(dict(sorted(commitments.items()))),
            government_policies=MappingProxyType(dict(sorted(policies.items())),),
            government_cases=MappingProxyType(dict(sorted(cases.items()))),
            government_tax_projects=MappingProxyType(dict(sorted(tax_projects.items()))),
            government_notices=MappingProxyType(dict(sorted(notices.items()))),
            social_relationships=MappingProxyType(dict(sorted(relationships.items()))),
            social_groups=MappingProxyType(dict(sorted(groups.items()))),
            social_conflicts=MappingProxyType(dict(sorted(conflicts.items()))),
            social_private_projections=MappingProxyType(dict(sorted(private_projections.items()))),
            population_signals=MappingProxyType(dict(sorted(signals.items()))),
            source_revision_vector=MappingProxyType(dict(sorted(revisions.items()))),
            projection_hash=digest,
        )

    @staticmethod
    def _validate_event(event: GameplayEvent, model: type[_Intent], stream_kind: str, privacy: str) -> None:
        prefix = {
            "organization": "gameplay:organization:", "government": "gameplay:government:",
            "government_case": "gameplay:government:case:", "social_relationship": "gameplay:social:relationship:",
            "social_group": "gameplay:social:group:", "social_case": "gameplay:social:case:",
            "social_private": "gameplay:social:private:", "population": "gameplay:social:population:",
        }[stream_kind]
        if not event.stream_id.startswith(prefix) or event.stream_revision < 1:
            raise OGSPlatformRuntimeError("ogs_stream_replay_invalid")
        if privacy == "project" and event.visibility_policy != "project":
            raise OGSPlatformRuntimeError("ogs_privacy_replay_invalid")
        if privacy == "authority_only" and event.visibility_policy != "authority_only":
            raise OGSPlatformRuntimeError("ogs_privacy_replay_invalid")
        if privacy == "public" and event.visibility_policy != "public":
            raise OGSPlatformRuntimeError("ogs_privacy_replay_invalid")
        try:
            parsed = model.model_validate(event.payload)
        except Exception as exc:
            raise OGSPlatformRuntimeError("ogs_payload_replay_invalid") from exc
        if any(getattr(parsed, field) is None for field in _ACTIVATION_PIN_FIELDS):
            raise OGSPlatformRuntimeError("ogs_activation_pins_replay_invalid")
        if (
            privacy == "actor_private"
            and (
                not isinstance(parsed, SocialPrivateProjectionIntent)
                or event.visibility_policy != f"actor:{parsed.participant_ref}"
            )
        ):
            raise OGSPlatformRuntimeError("ogs_privacy_replay_invalid")

    @staticmethod
    def _verify_checkpoint(checkpoint: OGSPlatformProjection) -> None:
        state = {
            "organization_lifecycles": dict(sorted(checkpoint.organization_lifecycles.items())),
            "organization_memberships": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.organization_memberships.items())},
            "organization_operating_periods": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.organization_operating_periods.items())},
            "organization_commitments": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.organization_commitments.items())},
            "government_policies": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.government_policies.items())},
            "government_cases": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.government_cases.items())},
            "government_tax_projects": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.government_tax_projects.items())},
            "government_notices": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.government_notices.items())},
            "social_relationships": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.social_relationships.items())},
            "social_groups": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.social_groups.items())},
            "social_conflicts": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.social_conflicts.items())},
            "social_private_projections": {key: value.model_dump(mode="json") for key, value in sorted(checkpoint.social_private_projections.items())},
            "population_signals": {
                key: value.model_dump(mode="json") for key, value in sorted(checkpoint.population_signals.items())
            },
            "source_revision_vector": dict(sorted(checkpoint.source_revision_vector.items())),
        }
        expected = "sha256:" + sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        if checkpoint.projection_hash != expected:
            raise OGSPlatformRuntimeError("ogs_checkpoint_tampered")


__all__ = [name for name in globals() if name.startswith(("Organization", "Government", "Social", "Population", "OGS_"))]
