from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.models import GameplayEvent
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from types import SimpleNamespace
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.organization_government_social_platform_runtime import (
    GOVERNMENT_CASE_STREAM_GRAMMAR,
    GOVERNMENT_JURISDICTION_STREAM_GRAMMAR,
    GOVERNMENT_NOTICE_STREAM_GRAMMAR,
    GOVERNMENT_TAX_TREASURY_STREAM_GRAMMAR,
    OGS_GOVERNMENT_PRINCIPAL_REF,
    OGS_ORGANIZATION_PRINCIPAL_REF,
    OGS_POPULATION_SIGNAL_EVENT_TYPE,
    OGS_POPULATION_SIGNAL_STREAM_GRAMMAR,
    OGS_PUBLIC_VISIBILITY_POLICY,
    OGS_SOCIAL_PRINCIPAL_REF,
    OGS_STREAM_GRAMMAR_PREFIXES,
    ORGANIZATION_COMMITMENT_STREAM_GRAMMAR,
    ORGANIZATION_LIFECYCLE_STREAM_GRAMMAR,
    ORGANIZATION_MEMBERSHIP_STREAM_GRAMMAR,
    ORGANIZATION_OPERATING_PERIOD_STREAM_GRAMMAR,
    OrganizationGovernmentSocialProjector,
    GovernmentNoticeAuditIntent,
    GovernmentNoticeAuditRecord,
    GovernmentPermitInspectionCaseIntent,
    GovernmentPermitInspectionCaseRecord,
    GovernmentPolicyLifecycleIntent,
    GovernmentPolicyLifecycleRecord,
    GovernmentTaxTreasuryProjectIntent,
    GovernmentTaxTreasuryProjectRecord,
    OrganizationCommitmentBudgetIntent,
    OrganizationCommitmentBudgetRecord,
    OrganizationLifecycleIntent,
    OrganizationLifecycleRecord,
    OrganizationMembershipDelegationIntent,
    OrganizationMembershipDelegationRecord,
    OrganizationOperatingPeriodIntent,
    OrganizationOperatingPeriodRecord,
    PopulationSignalMaterializationProposalIntent,
    PopulationSignalMaterializationProposalRecord,
    SocialHouseholdGroupIntent,
    SocialHouseholdGroupRecord,
    SocialIdentityRelationshipIntent,
    SocialIdentityRelationshipRecord,
    SocialNormConflictIntent,
    SocialNormConflictRecord,
    SocialPrivateProjectionIntent,
    SocialPrivateProjectionRecord,
)


def _event(
    event_type: str,
    stream_id: str,
    stream_revision: int,
    payload: dict[str, object],
    *,
    visibility_policy: str = "project",
    global_sequence: int | None = None,
) -> GameplayEvent:
    return GameplayEvent(
        event_id=f"event:{event_type}:{stream_revision}",
        event_type=event_type,
        schema_version=1,
        stream_id=stream_id,
        stream_revision=stream_revision,
        global_sequence=stream_revision if global_sequence is None else global_sequence,
        transaction_id=f"tx:{stream_id}",
        command_id=f"cmd:{stream_id}",
        causation_id=f"cause:{stream_id}",
        correlation_id=f"corr:{stream_id}",
        visibility_policy=visibility_policy,
        payload=payload,
    )


def _activation_pins() -> dict[str, str]:
    return {
        "package_revision_pin": "package:ogs@1",
        "content_digest_pin": "sha256:" + "a" * 64,
        "declaration_ref_pin": "declaration:ogs@1",
        "declaration_digest_pin": "sha256:" + "b" * 64,
        "descriptor_pin": "descriptor:ogs@1",
        "descriptor_revision_pin": "descriptor:ogs@1",
        "active_set_digest_pin": "sha256:" + "c" * 64,
    }


def test_ogs_runtime_accepts_canonical_intents_records_and_stream_grammars() -> None:
    assert OGS_ORGANIZATION_PRINCIPAL_REF == "actor_gameplay.organization_domain"
    assert OGS_GOVERNMENT_PRINCIPAL_REF == "actor_gameplay.government_domain"
    assert OGS_SOCIAL_PRINCIPAL_REF == "authority:p5:social"
    assert OGS_PUBLIC_VISIBILITY_POLICY == "public"
    assert OGS_POPULATION_SIGNAL_EVENT_TYPE == "gameplay.social.population_signal_recorded@1"
    assert ORGANIZATION_LIFECYCLE_STREAM_GRAMMAR == "gameplay:organization:{organization_ref}"
    assert ORGANIZATION_MEMBERSHIP_STREAM_GRAMMAR == "gameplay:organization:{organization_ref}"
    assert ORGANIZATION_OPERATING_PERIOD_STREAM_GRAMMAR == "gameplay:organization:{organization_ref}"
    assert ORGANIZATION_COMMITMENT_STREAM_GRAMMAR == "gameplay:organization:{organization_ref}"
    assert GOVERNMENT_JURISDICTION_STREAM_GRAMMAR == "gameplay:government:{jurisdiction_ref}"
    assert GOVERNMENT_CASE_STREAM_GRAMMAR == "gameplay:government:case:{case_ref}"
    assert GOVERNMENT_TAX_TREASURY_STREAM_GRAMMAR == "gameplay:government:{jurisdiction_ref}"
    assert GOVERNMENT_NOTICE_STREAM_GRAMMAR == "gameplay:government:{jurisdiction_ref}"
    assert OGS_POPULATION_SIGNAL_STREAM_GRAMMAR == "gameplay:social:population:{signal_ref}"
    assert OGS_STREAM_GRAMMAR_PREFIXES[0] == "gameplay:organization:"

    OrganizationLifecycleIntent.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "provenance_ref": "provenance:org-lifecycle@1",
            "source_revision_pin": 0,
            "from_state": "draft",
            "to_state": "active",
        }
    )
    OrganizationLifecycleRecord.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "provenance_ref": "provenance:org-lifecycle@1",
            "source_revision_pin": 0,
            "revision": 1,
            "from_state": "draft",
            "to_state": "active",
        }
    )
    OrganizationMembershipDelegationIntent.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "member_ref": "character:ada",
            "role_ref": "role:steward@1",
            "provenance_ref": "provenance:org-membership@1",
            "source_revision_pin": 0,
            "delegation_state": "delegated",
        }
    )
    OrganizationMembershipDelegationRecord.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "member_ref": "character:ada",
            "role_ref": "role:steward@1",
            "provenance_ref": "provenance:org-membership@1",
            "source_revision_pin": 0,
            "revision": 1,
            "delegation_state": "delegated",
        }
    )
    OrganizationOperatingPeriodIntent.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "period_ref": "period:2026-q3@1",
            "provenance_ref": "provenance:org-period@1",
            "source_revision_pin": 0,
            "period_state": "open",
            "opens_at_tick": 10,
            "closes_at_tick": 20,
        }
    )
    OrganizationOperatingPeriodRecord.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "period_ref": "period:2026-q3@1",
            "provenance_ref": "provenance:org-period@1",
            "source_revision_pin": 0,
            "revision": 1,
            "period_state": "open",
            "opens_at_tick": 10,
            "closes_at_tick": 20,
        }
    )
    OrganizationCommitmentBudgetIntent.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "budget_ref": "budget:millers@1",
            "provenance_ref": "provenance:org-budget@1",
            "source_revision_pin": 0,
            "budget_state": "proposed",
            "amount_minor": 250,
        }
    )
    OrganizationCommitmentBudgetRecord.model_validate(
        {
            "organization_ref": "organization:millers@1",
            "budget_ref": "budget:millers@1",
            "provenance_ref": "provenance:org-budget@1",
            "source_revision_pin": 0,
            "revision": 1,
            "budget_state": "proposed",
            "amount_minor": 250,
        }
    )
    GovernmentPolicyLifecycleIntent.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "policy_ref": "policy:riverward@1",
            "provenance_ref": "provenance:gov-policy@1",
            "source_revision_pin": 0,
            "policy_state": "active",
        }
    )
    GovernmentPolicyLifecycleRecord.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "policy_ref": "policy:riverward@1",
            "provenance_ref": "provenance:gov-policy@1",
            "source_revision_pin": 0,
            "revision": 1,
            "policy_state": "active",
        }
    )
    GovernmentPermitInspectionCaseIntent.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "case_ref": "case:permit@1",
            "provenance_ref": "provenance:gov-case@1",
            "source_revision_pin": 0,
            "case_state": "opened",
        }
    )
    GovernmentPermitInspectionCaseRecord.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "case_ref": "case:permit@1",
            "provenance_ref": "provenance:gov-case@1",
            "source_revision_pin": 0,
            "revision": 1,
            "case_state": "opened",
        }
    )
    GovernmentTaxTreasuryProjectIntent.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "project_ref": "project:tax@1",
            "provenance_ref": "provenance:gov-tax@1",
            "source_revision_pin": 0,
            "project_state": "proposed",
            "amount_minor": 500,
        }
    )
    GovernmentTaxTreasuryProjectRecord.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "project_ref": "project:tax@1",
            "provenance_ref": "provenance:gov-tax@1",
            "source_revision_pin": 0,
            "revision": 1,
            "project_state": "proposed",
            "amount_minor": 500,
        }
    )
    GovernmentNoticeAuditIntent.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "notice_ref": "notice:riverward@1",
            "provenance_ref": "provenance:gov-notice@1",
            "source_revision_pin": 0,
            "notice_state": "issued",
            "visibility_scope": "public",
        }
    )
    GovernmentNoticeAuditRecord.model_validate(
        {
            "jurisdiction_ref": "jurisdiction:riverward@1",
            "notice_ref": "notice:riverward@1",
            "provenance_ref": "provenance:gov-notice@1",
            "source_revision_pin": 0,
            "revision": 1,
            "notice_state": "issued",
            "visibility_scope": "public",
        }
    )
    SocialIdentityRelationshipIntent.model_validate(
        {
            "relationship_ref": "relationship:ada-bryn@1",
            "participant_refs": ("character:ada", "character:bryn"),
            "provenance_ref": "provenance:social-relationship@1",
            "source_revision_pin": 0,
            "relationship_state": "active",
        }
    )
    SocialIdentityRelationshipRecord.model_validate(
        {
            "relationship_ref": "relationship:ada-bryn@1",
            "participant_refs": ("character:ada", "character:bryn"),
            "provenance_ref": "provenance:social-relationship@1",
            "source_revision_pin": 0,
            "revision": 1,
            "relationship_state": "active",
        }
    )
    SocialHouseholdGroupIntent.model_validate(
        {
            "group_ref": "group:millers@1",
            "member_refs": ("character:ada", "character:bryn"),
            "provenance_ref": "provenance:social-household@1",
            "source_revision_pin": 0,
            "group_state": "forming",
        }
    )
    SocialHouseholdGroupRecord.model_validate(
        {
            "group_ref": "group:millers@1",
            "member_refs": ("character:ada", "character:bryn"),
            "provenance_ref": "provenance:social-household@1",
            "source_revision_pin": 0,
            "revision": 1,
            "group_state": "forming",
        }
    )
    SocialNormConflictIntent.model_validate(
        {
            "case_ref": "case:norm@1",
            "subject_refs": ("character:ada", "character:bryn"),
            "provenance_ref": "provenance:social-conflict@1",
            "source_revision_pin": 0,
            "conflict_state": "opened",
        }
    )
    SocialNormConflictRecord.model_validate(
        {
            "case_ref": "case:norm@1",
            "subject_refs": ("character:ada", "character:bryn"),
            "provenance_ref": "provenance:social-conflict@1",
            "source_revision_pin": 0,
            "revision": 1,
            "conflict_state": "opened",
        }
    )
    SocialPrivateProjectionIntent.model_validate(
        {
            "participant_ref": "character:ada",
            "provenance_ref": "provenance:social-private@1",
            "source_revision_pin": 0,
            "projection_state": "admitted",
            "visibility_scope": "actor_private",
        }
    )
    SocialPrivateProjectionRecord.model_validate(
        {
            "participant_ref": "character:ada",
            "provenance_ref": "provenance:social-private@1",
            "source_revision_pin": 0,
            "revision": 1,
            "projection_state": "admitted",
            "visibility_scope": "actor_private",
        }
    )
    PopulationSignalMaterializationProposalIntent.model_validate(
        {
            "signal_ref": "signal:riverward@1",
            "provenance_ref": "provenance:population@1",
            "source_revision_pin": 0,
            "materialization_state": "proposed",
            "visibility_scope": "public",
        }
    )
    PopulationSignalMaterializationProposalRecord.model_validate(
        {
            "signal_ref": "signal:riverward@1",
            "provenance_ref": "provenance:population@1",
            "source_revision_pin": 0,
            "revision": 1,
            "materialization_state": "proposed",
            "visibility_scope": "public",
        }
    )


def test_ogs_runtime_rejects_illegal_lifecycle_transition_and_private_population_signal() -> None:
    with pytest.raises(ValidationError):
        OrganizationLifecycleRecord.model_validate(
            {
                **_activation_pins(),
                "organization_ref": "organization:millers@1",
                "provenance_ref": "provenance:org-lifecycle@1",
                "source_revision_pin": 3,
                "revision": 4,
                "from_state": "closed",
                "to_state": "active",
            }
        )

    with pytest.raises(ValidationError):
        PopulationSignalMaterializationProposalIntent.model_validate(
            {
                **_activation_pins(),
                "signal_ref": "signal:riverward@1",
                "provenance_ref": "provenance:population@1",
                "source_revision_pin": 0,
                "materialization_state": "proposed",
                "visibility_scope": "private",
            }
        )


def test_ogs_runtime_rebuilds_tail_equal_and_fails_closed_on_tampering() -> None:
    projector = OrganizationGovernmentSocialProjector()
    events = [
        _event(
            "gameplay.organization.lifecycle_transitioned@1",
            "gameplay:organization:millers@1",
            1,
            {
                **_activation_pins(),
                "organization_ref": "organization:millers@1",
                "provenance_ref": "provenance:org-lifecycle@1",
                "source_revision_pin": 0,
                "from_state": "draft",
                "to_state": "active",
            },
        ),
        _event(
            "gameplay.social.population_signal_recorded@1",
            "gameplay:social:population:signal:riverward@1",
            1,
            {
                **_activation_pins(),
                "signal_ref": "signal:riverward@1",
                "provenance_ref": "provenance:population@1",
                "source_revision_pin": 0,
                "materialization_state": "proposed",
                "visibility_scope": "public",
            },
            visibility_policy="public",
            global_sequence=2,
        ),
        _event(
            "gameplay.social.identity_relationship_recorded@1",
            "gameplay:social:relationship:relationship:ada-bryn@1",
            1,
            {
                **_activation_pins(),
                "relationship_ref": "relationship:ada-bryn@1",
                "participant_refs": ("character:ada", "character:bryn"),
                "provenance_ref": "provenance:relationship@1",
                "source_revision_pin": 0,
                "relationship_state": "active",
            },
            global_sequence=3,
        ),
        _event(
            "gameplay.government.policy_lifecycle_recorded@1",
            "gameplay:government:jurisdiction:riverward@1",
            1,
            {
                **_activation_pins(),
                "jurisdiction_ref": "jurisdiction:riverward@1",
                "policy_ref": "policy:riverward-milling@1",
                "provenance_ref": "provenance:government-policy@1",
                "source_revision_pin": 0,
                "policy_state": "active",
            },
            global_sequence=4,
        ),
        _event(
            "gameplay.organization.membership_delegation_recorded@1",
            "gameplay:organization:millers@1",
            2,
            {
                **_activation_pins(),
                "organization_ref": "organization:millers@1",
                "member_ref": "character:ada",
                "role_ref": "role:steward@1",
                "provenance_ref": "provenance:membership@1",
                "source_revision_pin": 1,
                "delegation_state": "active",
            },
            global_sequence=5,
        ),
        _event(
            "gameplay.organization.operating_period_recorded@1",
            "gameplay:organization:millers@1",
            3,
            {
                **_activation_pins(),
                "organization_ref": "organization:millers@1", "period_ref": "period:spring@1",
                "provenance_ref": "provenance:period@1", "source_revision_pin": 2,
                "period_state": "open", "opens_at_tick": 10, "closes_at_tick": 20,
            },
            global_sequence=6,
        ),
        _event(
            "gameplay.government.permit_inspection_case_recorded@1",
            "gameplay:government:case:case:mill@1", 1,
            {**_activation_pins(), "jurisdiction_ref": "jurisdiction:riverward@1", "case_ref": "case:mill@1", "provenance_ref": "provenance:case@1", "source_revision_pin": 0, "case_state": "opened"},
            global_sequence=7,
        ),
        _event(
            "gameplay.social.household_group_recorded@1", "gameplay:social:group:group:millers@1", 1,
            {**_activation_pins(), "group_ref": "group:millers@1", "member_refs": ("character:ada", "character:bryn"), "provenance_ref": "provenance:group@1", "source_revision_pin": 0, "group_state": "active"}, global_sequence=8,
        ),
        _event(
            "gameplay.social.norm_conflict_recorded@1", "gameplay:social:case:case:mill-dispute@1", 1,
            {**_activation_pins(), "case_ref": "case:mill-dispute@1", "subject_refs": ("character:ada", "character:bryn"), "provenance_ref": "provenance:conflict@1", "source_revision_pin": 0, "conflict_state": "opened"}, global_sequence=9,
        ),
        _event(
            "gameplay.organization.commitment_budget_proposed@1", "gameplay:organization:millers@1", 4,
            {**_activation_pins(), "organization_ref": "organization:millers@1", "budget_ref": "budget:spring@1", "provenance_ref": "provenance:budget@1", "source_revision_pin": 3, "budget_state": "proposed", "amount_minor": 20}, global_sequence=10,
        ),
        _event(
            "gameplay.social.private_projection_recorded@1", "gameplay:social:private:character:ada", 1,
            {**_activation_pins(), "participant_ref": "character:ada", "provenance_ref": "provenance:private@1", "source_revision_pin": 0, "projection_state": "admitted", "visibility_scope": "actor_private"}, visibility_policy="actor:character:ada", global_sequence=11,
        ),
        _event(
            "gameplay.government.tax_treasury_project_proposed@1", "gameplay:government:jurisdiction:riverward@1", 2,
            {**_activation_pins(), "jurisdiction_ref": "jurisdiction:riverward@1", "project_ref": "project:tax@1", "provenance_ref": "provenance:tax@1", "source_revision_pin": 1, "project_state": "proposed", "amount_minor": 10}, visibility_policy="authority_only", global_sequence=12,
        ),
        _event(
            "gameplay.government.notice_audit_recorded@1", "gameplay:government:jurisdiction:riverward@1", 3,
            {**_activation_pins(), "jurisdiction_ref": "jurisdiction:riverward@1", "notice_ref": "notice:tax@1", "provenance_ref": "provenance:notice@1", "source_revision_pin": 2, "notice_state": "issued", "visibility_scope": "public"}, global_sequence=13,
        ),
    ]

    full = projector.rebuild(events)
    checkpoint = projector.rebuild(events[:11])
    tail = projector.rebuild(events[11:], checkpoint=checkpoint)

    assert full == tail
    assert full.source_revision_vector == tail.source_revision_vector
    assert full.social_relationships["relationship:ada-bryn@1"].relationship_state == "active"
    assert full.government_policies["policy:riverward-milling@1"].policy_state == "active"
    assert full.organization_memberships["organization:millers@1|character:ada"].delegation_state == "active"
    assert full.organization_operating_periods["organization:millers@1|period:spring@1"].period_state == "open"
    assert full.government_cases["case:mill@1"].case_state == "opened"
    assert full.social_groups["group:millers@1"].group_state == "active"
    assert full.social_conflicts["case:mill-dispute@1"].conflict_state == "opened"
    assert full.organization_commitments["budget:spring@1"].budget_state == "proposed"
    assert full.social_private_projections["character:ada"].projection_state == "admitted"
    assert full.government_tax_projects["project:tax@1"].project_state == "proposed"
    assert full.government_notices["notice:tax@1"].notice_state == "issued"

    tampered = checkpoint.model_copy(update={"projection_hash": "sha256:tampered"})
    with pytest.raises(ValueError):
        projector.rebuild(events[1:], checkpoint=tampered)

    unpinned = events[0].model_copy(update={"payload": {**events[0].payload, "active_set_digest_pin": None}}, deep=True)
    with pytest.raises(ValueError, match="ogs_activation_pins_replay_invalid"):
        projector.rebuild([unpinned])


def test_ogs_private_projection_replay_requires_its_exact_participant_scope() -> None:
    projector = OrganizationGovernmentSocialProjector()
    event = _event(
        "gameplay.social.private_projection_recorded@1",
        "gameplay:social:private:character:ada",
        1,
        {
            **_activation_pins(),
            "participant_ref": "character:ada",
            "provenance_ref": "provenance:private@1",
            "source_revision_pin": 0,
            "projection_state": "admitted",
            "visibility_scope": "actor_private",
        },
        visibility_policy="actor:character:bryn",
    )
    with pytest.raises(ValueError, match="ogs_privacy_replay_invalid"):
        projector.rebuild((event,))


def test_organization_lifecycle_has_no_unbound_platform_append_surface() -> None:
    assert not hasattr(OrganizationAuthority, "transition_platform_organization_lifecycle")
    assert hasattr(OrganizationAuthority, "transition_admitted_platform_organization_lifecycle")


def test_social_private_projection_without_active_binding_is_zero_write() -> None:
    social = SocialFactAuthority(
        registry=SimpleNamespace(registry_ref="registry:test", registry_revision="registry:test@1", registry_digest="sha256:" + "f" * 64),
        store=GameplayEventStore(),
    )
    result = social.record_admitted_platform_social_private_projection(
        intent={"participant_ref": "character:ada", "provenance_ref": "provenance:private@1", "source_revision_pin": 0, "projection_state": "admitted", "visibility_scope": "actor_private"},
        binding_ref="binding:missing@1", command_id="command:private", idempotency_key="idempotency:private", causation_id="cause:private", correlation_id="corr:private", expected_revision=0,
    )
    assert result.receipt is None
    assert result.resolution.result_kind == "rejected_zero_write"
