from __future__ import annotations

import pytest

from app.gameplay.debt_runtime import DebtAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError


def test_catalog_materializes_only_existing_cross_inf_owner_contracts() -> None:
    contracts = GovernedAuthorityContractCatalog.contracts()

    assert [contract.contract_ref for contract in contracts] == [
        "inf:construction-maintenance-state-expiry@1",
            "inf:ecology-drought-state-expiry@1",
            "inf:ecology-frost-state-expiry@1",
            "inf:economy-commerce-delivery-payment@1",
            "inf:economy-scheduled-transfer-policy@1",
        "inf:economy-tax-obligation@1",
        "inf:economy-wage-accrual-obligation@1",
        "inf:economy-wage-payment@1",
        "inf:government-failed-inspection-promotion@1",
        "inf:government-inspection-policy@1",
        "inf:government-inspection-promotion@1",
        "inf:organization-operating-window@1",
        "inf:organization-supply-promotion@1",
        "inf:simple-debt-settlement@1",
        "inf:survival-state-expiry@1",
        "inf:weather-front-construction-maintenance@1",
        "inf:weather-front-economy-quote-fanout@1",
        "inf:weather-front-economy-quote@1",
        "inf:weather-front-organization-supply-fanout@1",
        "inf:weather-front-organization-supply@1",
        "inf:weather-front-survival-cold@1",
        "inf:weather-front-survival-heat@1",
    ]
    assert [(contract.owner_ref, contract.projection_scope) for contract in contracts] == [
        ("actor_gameplay.construction_production_domain", "project"),
        ("authority:ecology", "project"),
        ("authority:ecology", "project"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.econ1_economy_domain", "project"),
        ("actor_gameplay.econ1_economy_domain", "mixed"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.organization_domain", "mixed"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.debt_domain", "authority_only"),
        ("actor_gameplay.survival_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.economy_domain", "project"),
        ("actor_gameplay.economy_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.survival_domain", "project"),
        ("actor_gameplay.survival_domain", "project"),
    ]


def test_catalog_rejects_unknown_or_kind_mismatched_contract_without_registration_surface() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_unknown"):
        GovernedAuthorityContractCatalog.require(contract_ref="inf:arbitrary-payment@1")
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_kind_mismatch"):
        GovernedAuthorityContractCatalog.require(
            contract_ref="inf:simple-debt-settlement@1",
            contract_kind="branch_promotion",
        )

    assert not hasattr(GovernedAuthorityContractCatalog, "register")
    assert not hasattr(GovernedAuthorityContractCatalog, "append")


def test_catalog_pins_existing_spine_metadata_for_each_cross_domain_contract() -> None:
    debt = GovernedAuthorityContractCatalog.require(contract_ref="inf:simple-debt-settlement@1")
    ecology = GovernedAuthorityContractCatalog.require(contract_ref="inf:weather-front-organization-supply@1")
    promotion = GovernedAuthorityContractCatalog.require(contract_ref="inf:organization-supply-promotion@1")

    assert debt.stream_patterns == (
        "gameplay:economy",
        "gameplay:contracts",
        "gameplay:debt",
        "gameplay:commerce",
    )
    assert debt.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert ecology.event_types == ("gameplay.organization.commerce_commitment_accepted",)
    assert ecology.replay_reader_ref == "OrganizationAuthority.commerce_commitment_projection"
    assert promotion.stream_patterns == ("gameplay:organization:{organization_ref}",)
    assert promotion.receipt_reader_ref == "OrganizationBranchPromotionReceipt"


def test_simple_debt_catalog_replay_reader_is_exposed_by_owner_service() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:simple-debt-settlement@1"
    )
    authority = DebtAuthorityService(store=GameplayEventStore())

    assert contract.replay_reader_ref == "DebtAuthorityService.replay_projection"
    assert callable(authority.replay_projection)


def test_catalog_pins_organization_operating_window_contract_metadata() -> None:
    window = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:organization-operating-window@1"
    )

    assert window.event_types == (
        "gameplay.organization.operating_window_opened",
        "gameplay.organization.operating_window_closed",
        "gameplay.organization.operating_window_due_recorded",
    )
    assert window.replay_reader_ref == "OrganizationAuthority._operating_window_state"


def test_catalog_pins_government_inspection_promotion_contract_metadata() -> None:
    promotion = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:government-inspection-promotion@1"
    )

    assert promotion.owner_ref == "actor_gameplay.government_domain"
    assert promotion.stream_patterns == ("gameplay:government:{organization_ref}",)
    assert promotion.event_types == ("gameplay.government.inspection_recorded",)
    assert promotion.projection_scope == "project"
    assert promotion.receipt_reader_ref == "GovernmentBranchPromotionReceipt"
    assert promotion.replay_reader_ref == "BranchPreviewAuthority.production_replay"


def test_catalog_pins_government_failed_inspection_promotion_contract_metadata() -> None:
    promotion = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:government-failed-inspection-promotion@1"
    )

    assert promotion.owner_ref == "actor_gameplay.government_domain"
    assert promotion.stream_patterns == ("gameplay:government:{organization_ref}",)
    assert promotion.event_types == ("gameplay.government.inspection_recorded",)
    assert promotion.projection_scope == "project"
    assert promotion.receipt_reader_ref == "GovernmentBranchPromotionReceipt"
    assert promotion.replay_reader_ref == "BranchPreviewAuthority.production_replay"


def test_catalog_pins_economy_wage_payment_contract_metadata() -> None:
    wage_payment = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:economy-wage-payment@1"
    )

    assert wage_payment.stream_patterns == (
        "gameplay:economy:wage:{worker_ref}",
        "gameplay:economy",
    )
    assert wage_payment.event_types == (
        "gameplay.economy.wage_paid",
        "gameplay.economy.account_debited",
        "gameplay.economy.account_credited",
    )
    assert wage_payment.projection_scope == "mixed"


def test_catalog_pins_weather_front_construction_consumer_contract_metadata() -> None:
    construction = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:weather-front-construction-maintenance@1"
    )

    assert construction.owner_ref == "actor_gameplay.construction_production_domain"
    assert construction.stream_patterns == ("gameplay:construction_production:{facility_ref}",)
    assert construction.event_types == (
        "gameplay.construction_production.maintenance_obligation_created",
    )
    assert construction.projection_scope == "project"


def test_catalog_pins_weather_front_organization_consumer_contract_metadata() -> None:
    organization = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:weather-front-organization-supply@1"
    )

    assert organization.owner_ref == "actor_gameplay.organization_domain"
    assert organization.stream_patterns == ("gameplay:organization:{organization_ref}",)
    assert organization.event_types == ("gameplay.organization.commerce_commitment_accepted",)
    assert organization.replay_reader_ref == "OrganizationAuthority.commerce_commitment_projection"


def test_catalog_pins_weather_front_organization_fanout_consumer_contract_metadata() -> None:
    organization = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:weather-front-organization-supply-fanout@1"
    )

    assert organization.owner_ref == "actor_gameplay.organization_domain"
    assert organization.stream_patterns == ("gameplay:organization:{organization_ref}",)
    assert organization.event_types == ("gameplay.organization.commerce_commitment_accepted",)
    assert organization.projection_scope == "project"
    assert organization.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert organization.replay_reader_ref == "OrganizationAuthority.commerce_commitment_projection"


def test_catalog_pins_weather_front_economy_quote_consumer_contract_metadata() -> None:
    economy = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:weather-front-economy-quote@1"
    )

    assert economy.owner_ref == "actor_gameplay.economy_domain"
    assert economy.stream_patterns == ("gameplay:economy",)
    assert economy.event_types == ("gameplay.economy.dynamic_quote_published",)
    assert economy.replay_reader_ref == "EconomyProjector"


def test_catalog_pins_weather_front_economy_quote_fanout_consumer_contract_metadata() -> None:
    economy = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:weather-front-economy-quote-fanout@1"
    )

    assert economy.owner_ref == "actor_gameplay.economy_domain"
    assert economy.stream_patterns == ("gameplay:economy",)
    assert economy.event_types == ("gameplay.economy.dynamic_quote_published",)
    assert economy.projection_scope == "project"
    assert economy.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert economy.replay_reader_ref == "EconomyProjector"


def test_catalog_rejects_owner_stream_event_or_privacy_mismatch() -> None:
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_owner_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:government-inspection-policy@1",
            contract_kind="policy",
            owner_ref="caller",
            stream_ids=("gameplay:government:organization:catalog",),
            event_types=("gameplay.government.commercial_inspection_policy_registered",),
            projection_scope="project",
        )
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_stream_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:organization-supply-promotion@1",
            contract_kind="branch_promotion",
            owner_ref="actor_gameplay.organization_domain",
            stream_ids=("gameplay:government:organization:catalog",),
            event_types=("gameplay.organization.commerce_commitment_accepted",),
            projection_scope="project",
        )
    with pytest.raises(GovernedAuthorityContractError, match="governed_authority_contract_event_mismatch"):
        GovernedAuthorityContractCatalog.require_operation(
            contract_ref="inf:weather-front-organization-supply@1",
            contract_kind="ecology_consumer",
            owner_ref="actor_gameplay.organization_domain",
            stream_ids=("gameplay:organization:organization:catalog",),
            event_types=("gameplay.organization.role_assigned",),
            projection_scope="project",
        )
