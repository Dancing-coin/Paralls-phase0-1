from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.gameplay.debt_runtime import DebtAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import (
    GovernedAuthorityContractCatalog,
    GovernedAuthorityContractError,
    OwnerOperationDescriptor,
)
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry


def test_catalog_materializes_only_existing_cross_inf_owner_contracts() -> None:
    contracts = tuple(
        contract
        for contract in GovernedAuthorityContractCatalog.contracts()
        if contract.contract_ref not in {
            "inf:organization-public-project-execution@1",
            "inf:government-public-project-execution-acknowledgment@1",
            "inf:ecology-weather-rain-crop-recovery@1",
            "inf:ecology-weather-rain-water-resource-recovery@1",
                "inf:ecology-grain-harvest@1",
                "inf:inventory-grain-harvest-custody@1",
            "inf:construction-facility-mill-reinforced-public-use@1",
            "inf:construction-reinforced-mill-flour-output-certification@1",
            "inf:industrial-facility-reinforced-mill-flour-output-purchase@1",
            "inf:industrial-facility-public-milling-session-contract-admission@1",
            "inf:industrial-facility-public-milling-session-contract-fulfillment@1",
            "inf:organization-public-milling-activity@1",
                "inf:government-public-milling-notice@1",
                    "inf:social-public-milling-notice-acknowledgment@1",
                    "inf:organization-grain-intake@1",
                "inf:economy-grain-intake-acceptance@1",
                "inf:construction-recipe-production@1",
            }
        )

    assert [contract.contract_ref for contract in contracts] == [
        "inf:branch-work-wage-admission@1",
        "inf:construction-facility-bakery-reinforcement@1",
        "inf:construction-facility-mill-decommission@1",
        "inf:construction-facility-mill-reinforcement@1",
        "inf:construction-facility-operational-verification@1",
        "inf:construction-facility-package-declared-transform@1",
        "inf:construction-facility-public-use-enable@1",
        "inf:construction-facility-repair@1",
        "inf:construction-maintenance-state-expiry@1",
        "inf:construction-public-project-step-completion@1",
        "inf:contract-completed-municipal-drought-assessment-certificate@1",
            "inf:ecology-drought-state-expiry@1",
            "inf:ecology-frost-state-expiry@1",
        "inf:economy-commerce-delivery-payment@1",
        "inf:economy-government-tax-payment@1",
        "inf:economy-production-output-market-eligibility@1",
        "inf:economy-public-project-budget-close@1",
        "inf:economy-public-project-budget-commitment@1",
        "inf:economy-public-project-budget-consumption@1",
        "inf:economy-public-project-budget-reservation@1",
        "inf:economy-scheduled-transfer-policy@1",
        "inf:economy-tax-obligation@1",
        "inf:economy-wage-accrual-obligation@1",
        "inf:economy-wage-payment@1",
        "inf:facility-commissioning-review-contract-admission@1",
        "inf:facility-commissioning-review-contract-fulfillment@1",
        "inf:government-drought-advisory-municipal-assessment-contract@1",
        "inf:government-failed-inspection-promotion@1",
        "inf:government-inspection-policy@1",
        "inf:government-inspection-promotion@1",
        "inf:government-public-workshop-notice@1",
        "inf:government-treasury-collector@1",
        "inf:municipal-drought-assessment-contract-fulfillment@1",
        "inf:organization-operating-window@1",
        "inf:organization-production-work-contribution-acceptance@1",
        "inf:organization-production-work-order-fulfillment@1",
        "inf:organization-public-workshop-activity@1",
        "inf:organization-supply-promotion@1",
        "inf:ownership-certificate-government-drought-assessment-acknowledgment@1",
        "inf:package-declared-negotiated-exchange@1",
        "inf:public-workshop-session-contract-admission@1",
        "inf:public-workshop-session-contract-fulfillment@1",
        "inf:simple-debt-settlement@1",
        "inf:social-handshake-shared-experience@1",
        "inf:survival-state-expiry@1",
        "inf:weather-front-construction-maintenance@1",
        "inf:weather-front-economy-quote-fanout@1",
        "inf:weather-front-economy-quote@1",
        "inf:weather-front-government-drought-advisory@1",
        "inf:weather-front-organization-supply-fanout@1",
        "inf:weather-front-organization-supply@1",
        "inf:weather-front-survival-cold@1",
        "inf:weather-front-survival-dehydration@1",
        "inf:weather-front-survival-heat@1",
        "inf:weather-front-survival-hydration@1",
    ]
    assert [(contract.owner_ref, contract.projection_scope) for contract in contracts] == [
        ("actor_gameplay.econ1_economy_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.ownership_domain", "authority_only"),
        ("authority:ecology", "project"),
        ("authority:ecology", "project"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.econ1_economy_domain", "project"),
        ("actor_gameplay.econ1_economy_domain", "mixed"),
        ("actor_gameplay.contract_domain", "authority_only"),
        ("actor_gameplay.contract_domain", "authority_only"),
        ("actor_gameplay.contract_domain", "authority_only"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.government_treasury_collector", "authority_only"),
        ("actor_gameplay.contract_domain", "authority_only"),
        ("actor_gameplay.organization_domain", "mixed"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.government_domain", "authority_only"),
        ("actor_gameplay.economy_domain", "authority_only"),
        ("actor_gameplay.contract_domain", "authority_only"),
        ("actor_gameplay.contract_domain", "authority_only"),
        ("actor_gameplay.debt_domain", "authority_only"),
        ("authority:p5:social", "actor_private"),
        ("actor_gameplay.survival_domain", "project"),
        ("actor_gameplay.construction_production_domain", "project"),
        ("actor_gameplay.economy_domain", "project"),
        ("actor_gameplay.economy_domain", "project"),
        ("actor_gameplay.government_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.organization_domain", "project"),
        ("actor_gameplay.survival_domain", "project"),
        ("actor_gameplay.survival_domain", "project"),
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


def test_catalog_pins_exact_public_project_budget_reservation_row() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:economy-public-project-budget-reservation@1",
        contract_kind="settlement",
    )
    assert contract.owner_ref == "actor_gameplay.economy_domain"
    assert contract.stream_patterns == ("gameplay:economy",)
    assert contract.event_types == ("gameplay.economy.budget_reserved",)
    assert contract.projection_scope == "authority_only"
    assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert contract.replay_reader_ref == "EconomyAuthorityService.public_project_budget_reservation_projection"

    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref == "descriptor:economy-public-project-budget-reservation@1"
    )
    assert descriptor.capability_ref == "capability:economy-public-project-budget-reservation@1"
    assert descriptor.outcome_family_ref == "outcome:economy-public-project-budget-reserved@1"
    assert descriptor.allowed_predicate_family_refs == (
        "predicate:economy-public-project-commitment-owner-account@1",
    )
    assert descriptor.allowed_proposal_effect_types == (
        "effect:economy-public-project-budget-reserved@1",
    )


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


def test_catalog_pins_admitted_construction_and_government_descriptors() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:construction-facility-package-declared-transform@1",
        contract_kind="settlement",
    )

    assert contract.owner_ref == "actor_gameplay.construction_production_domain"
    assert contract.stream_patterns == ("gameplay:construction_production:{facility_ref}",)
    assert contract.event_types == ("gameplay.construction_production.facility_transformed",)
    assert contract.projection_scope == "project"
    assert contract.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert contract.replay_reader_ref == "ConstructionProductionAuthority.projector"

    assert tuple(
        descriptor
        for descriptor in GovernedAuthorityContractCatalog.descriptors()
        if descriptor.descriptor_ref not in {
            "descriptor:organization-public-project-execution@1",
            "descriptor:government-public-project-execution-acknowledgment@1",
            "descriptor:ecology-weather-rain-crop-recovery@1",
            "descriptor:ecology-weather-rain-water-resource-recovery@1",
                "descriptor:ecology-grain-harvest@1",
                "descriptor:inventory-grain-harvest-custody@1",
                "descriptor:construction-reinforced-mill-flour-output-certification@1",
                "descriptor:industrial-facility-reinforced-mill-flour-output-purchase@1",
            "descriptor:industrial-facility-public-milling-session-contract-admission@1",
            "descriptor:industrial-facility-public-milling-session-contract-fulfillment@1",
            "descriptor:organization-public-milling-activity@1",
            "descriptor:government-public-milling-notice@1",
                "descriptor:social-public-milling-notice-acknowledgment@1",
                "descriptor:organization-grain-intake@1",
                    "descriptor:economy-grain-intake-acceptance@1",
                    "descriptor:construction-recipe-production@1",
                    "descriptor:construction-blueprint-placement@1",
        }
    ) == (
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-facility-package-declared-transform@1",
            descriptor_revision="descriptor:construction-facility-package-declared-transform@1",
            capability_ref="capability:construction-facility-package-declared-transform@1",
            outcome_family_ref="outcome:construction-facility-package-declared-transform@1",
            allowed_predicate_family_refs=("predicate:construction-facility-acquired@1",),
            allowed_proposal_effect_types=(
                    "effect:construction-facility-package-declared-transform@1",
                ),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:economy-production-output-market-eligibility@1",
                family_ref=None,
                descriptor_revision="descriptor:economy-production-output-market-eligibility@1",
                capability_ref="capability:economy-production-output-market-eligibility@1",
                outcome_family_ref="outcome:economy-production-output-market-eligibility@1",
                allowed_predicate_family_refs=("predicate:inventory-production-output-custody@1",),
                allowed_proposal_effect_types=("effect:economy-production-output-market-eligibility@1",),
                owner_ref="actor_gameplay.economy_domain",
                accepted_intent_schema_ref="schema:economy-production-output-market-eligibility-intent@1",
                source_event_types=("gameplay.inventory.production_output_received@1",),
                source_stream_pattern="gameplay:inventory:{holder_ref}",
                source_revision_fence_ref="revision:inventory-production-output-custody@1",
                target_stream_pattern="gameplay:economy",
                target_event_types=("gameplay.economy.production_output_market_eligible@1",),
                privacy_scope="authority_only",
                idempotency_rule_ref="idempotency:economy-production-output-market-eligibility@1",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_refs=(
                    "reader:economy-production-output-market-eligibility-checkpoint-tail@1",
                    "reader:economy-production-output-market-eligibility-full@1",
                ),
                terminal_semantics_ref="lifecycle:terminal-no-compensation@1",
                reversal_semantics_ref="lifecycle:none@1",
                compensation_semantics_ref="lifecycle:none@1",
                allowed_recipe_family_refs=(),
                package_slot_refs=(),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-facility-mill-reinforcement@1",
                descriptor_revision="descriptor:construction-facility-mill-reinforcement@1",
                capability_ref="capability:construction-facility-mill-reinforcement@1",
                outcome_family_ref="outcome:construction-facility-mill-reinforcement@1",
                allowed_predicate_family_refs=("predicate:construction-facility-acquired@1",),
                allowed_proposal_effect_types=("effect:construction-facility-mill-reinforcement@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-facility-mill-decommission@1",
                descriptor_revision="descriptor:construction-facility-mill-decommission@1",
                capability_ref="capability:construction-facility-mill-decommission@1",
                outcome_family_ref="outcome:construction-facility-mill-decommission@1",
                allowed_predicate_family_refs=("predicate:construction-facility-mill-reinforced@1",),
                allowed_proposal_effect_types=("effect:construction-facility-mill-decommission@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-facility-operational-verification@1",
                descriptor_revision="descriptor:construction-facility-operational-verification@1",
                capability_ref="capability:construction-facility-operational-verification@1",
                outcome_family_ref="outcome:construction-facility-operationally-verified@1",
                allowed_predicate_family_refs=("predicate:construction-production-run-completed@1",),
                allowed_proposal_effect_types=("effect:construction-facility-operationally-verified@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-facility-public-use-enable@1",
                descriptor_revision="descriptor:construction-facility-public-use-enable@1",
                capability_ref="capability:construction-facility-public-use-enable@1",
                outcome_family_ref="outcome:construction-facility-public-use-enabled@1",
                allowed_predicate_family_refs=("predicate:construction-facility-operationally-verified@1",),
                allowed_proposal_effect_types=("effect:construction-facility-public-use-enabled@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-facility-mill-reinforced-public-use-enable@1",
                descriptor_revision="descriptor:construction-facility-mill-reinforced-public-use-enable@1",
                capability_ref="capability:construction-facility-mill-reinforced-public-use-enable@1",
                outcome_family_ref="outcome:construction-facility-mill-reinforced-public-use-enabled@1",
                allowed_predicate_family_refs=("predicate:construction-facility-mill-reinforced-operationally-verified@1",),
                allowed_proposal_effect_types=("effect:construction-facility-mill-reinforced-public-use-enabled@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:construction-public-project-step-completion@1",
                descriptor_revision="descriptor:construction-public-project-step-completion@1",
                capability_ref="capability:construction-public-project-step-completion@1",
                outcome_family_ref="outcome:construction-public-project-step-completed@1",
                allowed_predicate_family_refs=("predicate:organization-public-project-work-order-fulfilled@1",),
                allowed_proposal_effect_types=("effect:construction-public-project-step-completed@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:government-drought-advisory@1",
                descriptor_revision="descriptor:government-drought-advisory@1",
                capability_ref="capability:government-drought-advisory@1",
                outcome_family_ref="outcome:government-drought-advisory@1",
                allowed_predicate_family_refs=("predicate:ecology-weather-front-drought@1",),
                allowed_proposal_effect_types=("effect:government-drought-advisory@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:government-drought-assessment-acknowledgment@1",
                descriptor_revision="descriptor:government-drought-assessment-acknowledgment@1",
                capability_ref="capability:government-drought-assessment-acknowledgment@1",
                outcome_family_ref="outcome:government-drought-assessment-acknowledged@1",
                allowed_predicate_family_refs=(
                    "predicate:ownership-municipal-drought-assessment-certificate@1",
                ),
                allowed_proposal_effect_types=(
                    "effect:government-drought-assessment-acknowledged@1",
                ),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:municipal-drought-assessment-fulfillment@1",
                descriptor_revision="descriptor:municipal-drought-assessment-fulfillment@1",
                capability_ref="capability:municipal-drought-assessment-fulfillment@1",
                outcome_family_ref="outcome:municipal-drought-assessment-fulfilled@1",
                allowed_predicate_family_refs=(
                    "predicate:contract-municipal-drought-assessment-active@1",
                ),
                allowed_proposal_effect_types=(
                    "effect:municipal-drought-assessment-fulfilled@1",
                ),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:facility-commissioning-review-contract-admission@1",
                descriptor_revision="descriptor:facility-commissioning-review-contract-admission@1",
                capability_ref="capability:facility-commissioning-review@1",
                outcome_family_ref="outcome:facility-commissioning-review-contract@1",
                allowed_predicate_family_refs=("predicate:construction-facility-operationally-verified@1",),
                allowed_proposal_effect_types=("effect:facility-commissioning-review-contract-created@1",),
            ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:facility-commissioning-review-contract-fulfillment@1",
                descriptor_revision="descriptor:facility-commissioning-review-contract-fulfillment@1",
                capability_ref="capability:facility-commissioning-review@1",
                outcome_family_ref="outcome:facility-commissioning-review-contract@1",
                allowed_predicate_family_refs=("predicate:facility-commissioning-review-active@1",),
                    allowed_proposal_effect_types=("effect:facility-commissioning-review-fulfilled@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:public-workshop-session-contract-admission@1",
                    descriptor_revision="descriptor:public-workshop-session-contract-admission@1",
                    capability_ref="capability:public-workshop-session@1",
                    outcome_family_ref="outcome:public-workshop-session-contract@1",
                    allowed_predicate_family_refs=("predicate:construction-facility-public-use-enabled@1",),
                    allowed_proposal_effect_types=("effect:public-workshop-session-contract-created@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:public-workshop-session-contract-fulfillment@1",
                    descriptor_revision="descriptor:public-workshop-session-contract-fulfillment@1",
                    capability_ref="capability:public-workshop-session@1",
                    outcome_family_ref="outcome:public-workshop-session-contract@1",
                    allowed_predicate_family_refs=("predicate:public-workshop-session-active@1",),
                    allowed_proposal_effect_types=("effect:public-workshop-session-fulfilled@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:organization-public-workshop-activity@1",
                    descriptor_revision="descriptor:organization-public-workshop-activity@1",
                    capability_ref="capability:organization-public-workshop-activity@1",
                    outcome_family_ref="outcome:organization-public-workshop-activity-recorded@1",
                    allowed_predicate_family_refs=("predicate:contract-public-workshop-session-fulfilled@1",),
                    allowed_proposal_effect_types=("effect:organization-public-workshop-activity-recorded@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:government-public-workshop-notice@1",
                    descriptor_revision="descriptor:government-public-workshop-notice@1",
                    capability_ref="capability:government-public-workshop-notice@1",
                    outcome_family_ref="outcome:government-public-workshop-notice-recorded@1",
                    allowed_predicate_family_refs=("predicate:organization-public-workshop-activity-completed@1",),
                    allowed_proposal_effect_types=("effect:government-public-workshop-notice-recorded@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:social-handshake-shared-experience@1",
                    descriptor_revision="descriptor:social-handshake-shared-experience@1",
                    capability_ref="capability:social-handshake-shared-experience@1",
                    outcome_family_ref="outcome:social-handshake-shared-experience-recorded@1",
                    allowed_predicate_family_refs=("predicate:embodied-completed-two-party-handshake@1",),
                    allowed_proposal_effect_types=("effect:social-handshake-shared-experience-recorded@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:organization-production-work-contribution-acceptance@1",
                    descriptor_revision="descriptor:organization-production-work-contribution-acceptance@1",
                    capability_ref="capability:organization-production-work-contribution-acceptance@1",
                    outcome_family_ref="outcome:organization-production-work-contribution-accepted@1",
                    allowed_predicate_family_refs=(
                        "predicate:production-completed-evidence-bound-to-organization-schedule@1",
                    ),
                    allowed_proposal_effect_types=(
                        "effect:organization-production-work-contribution-accepted@1",
                    ),
                ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:organization-production-work-order-fulfillment@1",
                    descriptor_revision="descriptor:organization-production-work-order-fulfillment@1",
                    capability_ref="capability:organization-production-work-order-fulfillment@1",
                    outcome_family_ref="outcome:organization-production-work-order-fulfilled@1",
                    allowed_predicate_family_refs=(
                        "predicate:organization-work-contribution-accepted@1",
                    ),
                    allowed_proposal_effect_types=(
                        "effect:organization-production-work-order-fulfilled@1",
                    ),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:economy-public-project-budget-commitment@1",
                    descriptor_revision="descriptor:economy-public-project-budget-commitment@1",
                    capability_ref="capability:economy-public-project-budget-commitment@1",
                    outcome_family_ref="outcome:economy-public-project-budget-commitment-recorded@1",
                    allowed_predicate_family_refs=("predicate:construction-public-project-step-completed@1",),
                    allowed_proposal_effect_types=("effect:economy-public-project-budget-commitment-recorded@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:economy-public-project-budget-reservation@1",
                    descriptor_revision="descriptor:economy-public-project-budget-reservation@1",
                    capability_ref="capability:economy-public-project-budget-reservation@1",
                    outcome_family_ref="outcome:economy-public-project-budget-reserved@1",
                    allowed_predicate_family_refs=("predicate:economy-public-project-commitment-owner-account@1",),
                    allowed_proposal_effect_types=("effect:economy-public-project-budget-reserved@1",),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:economy-public-project-budget-consumption@1",
                    descriptor_revision="descriptor:economy-public-project-budget-consumption@1",
                    capability_ref="capability:economy-public-project-budget-consumption@1",
                    outcome_family_ref="outcome:economy-public-project-budget-consumed@1",
                    allowed_predicate_family_refs=(
                        "predicate:economy-public-project-budget-reserved-and-workshop-activity@1",
                    ),
                    allowed_proposal_effect_types=(
                        "effect:economy-public-project-budget-consumed@1",
                    ),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:economy-public-project-budget-close@1",
                    descriptor_revision="descriptor:economy-public-project-budget-close@1",
                    capability_ref="capability:economy-public-project-budget-close@1",
                    outcome_family_ref="outcome:economy-public-project-budget-closed@1",
                    allowed_predicate_family_refs=(
                        "predicate:economy-public-project-budget-consumed-and-project-executed@1",
                    ),
                    allowed_proposal_effect_types=(
                        "effect:economy-public-project-budget-closed@1",
                    ),
                ),
                OwnerOperationDescriptor(
                    descriptor_ref="descriptor:weather-front-survival-hydration@1",
                    descriptor_revision="descriptor:weather-front-survival-hydration@1",
                    capability_ref="capability:weather-front-survival-hydration@1",
                    outcome_family_ref="outcome:weather-front-survival-hydration@1",
                    allowed_predicate_family_refs=("predicate:ecology-weather-front-rain@1",),
                    allowed_proposal_effect_types=("effect:weather-front-survival-hydration@1",),
                ),
                )

    advisory = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:weather-front-government-drought-advisory@1",
        contract_kind="ecology_consumer",
    )
    assert advisory.owner_ref == "actor_gameplay.government_domain"
    assert advisory.stream_patterns == ("gameplay:government:advisory:{jurisdiction_ref}",)
    assert advisory.event_types == ("gameplay.government.drought_advisory_issued",)
    assert advisory.projection_scope == "project"
    assert advisory.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert advisory.replay_reader_ref == "GovernmentAuthority.drought_advisory_view_for"


def test_frozen_inf_1ag_package_binds_to_the_one_admitted_descriptor_without_construction_write() -> None:
    manifest_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "superpowers"
        / "specs"
        / "world-character-siming-authority-mainline"
        / "inf-1"
        / "package-industrial-facilities-v1.manifest.json"
    )
    manifest = GameplayPatchManifest.model_validate(json.loads(manifest_path.read_text(encoding="utf-8")))
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))

    registry.install(manifest)
    active = registry.activate((manifest.patch_revision_id,))

    assert len(active.capability_bindings) == 1
    binding = active.capability_bindings[0]
    assert binding.binding_ref == "binding:industrial-facilities-oven-to-kiln@1"
    assert binding.package_revision == "package:industrial-facilities:v1"
    assert binding.content_digest == manifest.content_digest
    assert binding.declaration_digest == manifest.platform_extension.outcome_declarations[0].declaration_digest
    assert binding.descriptor_ref == "descriptor:construction-facility-package-declared-transform@1"
    assert binding.descriptor_revision == "descriptor:construction-facility-package-declared-transform@1"


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
