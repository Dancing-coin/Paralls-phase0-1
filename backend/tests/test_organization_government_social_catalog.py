from __future__ import annotations

from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog


def test_ogs_catalog_has_closed_owner_bound_family_portfolio() -> None:
    expected = {
        "inf:organization-lifecycle@1": "actor_gameplay.organization_domain",
        "inf:organization-membership-delegation@1": "actor_gameplay.organization_domain",
        "inf:organization-operating-period@1": "actor_gameplay.organization_domain",
        "inf:organization-commitment-budget@1": "actor_gameplay.organization_domain",
        "inf:government-jurisdiction-policy@1": "actor_gameplay.government_domain",
        "inf:government-permit-inspection-enforcement@1": "actor_gameplay.government_domain",
        "inf:government-tax-treasury-project@1": "actor_gameplay.government_domain",
        "inf:government-notice-audit@1": "actor_gameplay.government_domain",
        "inf:social-identity-relationship@1": "authority:p5:social",
        "inf:social-household-group@1": "authority:p5:social",
        "inf:social-norm-conflict@1": "authority:p5:social",
        "inf:social-private-projection@1": "authority:p5:social",
        "inf:population-signal-materialization@1": "authority:p5:social",
    }

    for contract_ref, owner_ref in expected.items():
        contract = GovernedAuthorityContractCatalog.require(contract_ref=contract_ref)
        assert contract.owner_ref == owner_ref
        assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
        assert contract.replay_reader_ref.startswith("OrganizationGovernmentSocialProjector.")


def test_ogs_descriptors_fix_owner_stream_event_and_replay_coordinates() -> None:
    descriptors = {
        item.family_ref: item
        for item in GovernedAuthorityContractCatalog.all_descriptors()
        if item.family_ref in {
            "organization_lifecycle@1",
            "government_jurisdiction_policy@1",
            "social_identity_relationship@1",
            "population_signal_materialization@1",
        }
    }

    assert descriptors["organization_lifecycle@1"].target_stream_pattern == "gameplay:organization:{organization_ref}"
    assert descriptors["government_jurisdiction_policy@1"].target_stream_pattern == "gameplay:government:{jurisdiction_ref}"
    assert descriptors["social_identity_relationship@1"].target_stream_pattern == "gameplay:social:relationship:{relationship_ref}"
    assert descriptors["population_signal_materialization@1"].target_event_types == (
        "gameplay.social.population_signal_recorded@1",
    )
