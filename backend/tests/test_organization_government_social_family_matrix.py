from __future__ import annotations

from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.organization_government_social_content import content_model_for_ogs_family


FAMILIES = {
    "organization_lifecycle@1": ("descriptor:organization-lifecycle@1", "gameplay.organization.lifecycle_transitioned@1"),
    "organization_membership_delegation@1": ("descriptor:organization-membership-delegation@1", "gameplay.organization.membership_delegation_recorded@1"),
    "organization_operating_period@1": ("descriptor:organization-operating-period@1", "gameplay.organization.operating_period_recorded@1"),
    "organization_commitment_budget@1": ("descriptor:organization-commitment-budget@1", "gameplay.organization.commitment_budget_proposed@1"),
    "government_jurisdiction_policy@1": ("descriptor:government-jurisdiction-policy@1", "gameplay.government.policy_lifecycle_recorded@1"),
    "government_permit_inspection_enforcement@1": ("descriptor:government-permit-inspection-enforcement@1", "gameplay.government.permit_inspection_case_recorded@1"),
    "government_tax_treasury_project@1": ("descriptor:government-tax-treasury-project@1", "gameplay.government.tax_treasury_project_proposed@1"),
    "government_notice_audit@1": ("descriptor:government-notice-audit@1", "gameplay.government.notice_audit_recorded@1"),
    "social_identity_relationship@1": ("descriptor:social-identity-relationship@1", "gameplay.social.identity_relationship_recorded@1"),
    "social_household_group@1": ("descriptor:social-household-group@1", "gameplay.social.household_group_recorded@1"),
    "social_norm_conflict@1": ("descriptor:social-norm-conflict@1", "gameplay.social.norm_conflict_recorded@1"),
    "social_private_projection@1": ("descriptor:social-private-projection@1", "gameplay.social.private_projection_recorded@1"),
    "population_signal_materialization@1": ("descriptor:population-signal-materialization@1", "gameplay.social.population_signal_recorded@1"),
}


def test_every_ogs_family_has_descriptor_contract_event_and_content_model() -> None:
    for family_ref, (descriptor_ref, event_type) in FAMILIES.items():
        descriptor = GovernedAuthorityContractCatalog.require_descriptor(descriptor_ref)
        assert descriptor.family_ref == family_ref
        assert descriptor.target_event_types == (event_type,)
        assert len(descriptor.replay_reader_refs) == 2
        assert all(ref.startswith("reader:") for ref in descriptor.replay_reader_refs)
        assert content_model_for_ogs_family(family_ref) is not None
        contract = GovernedAuthorityContractCatalog.require(contract_ref=f"inf:{descriptor_ref.removeprefix('descriptor:')}")
        assert event_type in contract.event_types
