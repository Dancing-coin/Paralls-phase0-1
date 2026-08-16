from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel


class GovernedAuthorityContractError(ValueError):
    pass


class GovernedAuthorityContract(StrictGameplayModel):
    """Read-only cross-INF admission metadata for an already-existing owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ref: str = Field(min_length=1)
    contract_kind: Literal["lifecycle", "policy", "settlement", "ecology_consumer", "branch_promotion"]
    owner_ref: str = Field(min_length=1)
    stream_patterns: tuple[str, ...] = Field(min_length=1)
    event_types: tuple[str, ...] = Field(min_length=1)
    projection_scope: Literal["project", "authority_only", "mixed"]
    receipt_reader_ref: str = Field(min_length=1)
    replay_reader_ref: str = Field(min_length=1)


class GovernedAuthorityContractCatalog:
    """A frozen catalog. It neither registers contracts nor writes world truth."""

    @staticmethod
    def contracts() -> tuple[GovernedAuthorityContract, ...]:
        contracts = (
            GovernedAuthorityContract(
                contract_ref="inf:economy-wage-payment@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.econ1_economy_domain",
                stream_patterns=(
                    "gameplay:economy:wage:{worker_ref}",
                    "gameplay:economy",
                ),
                event_types=(
                    "gameplay.economy.wage_paid",
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                ),
                projection_scope="mixed",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-commerce-delivery-payment@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.commerce_delivery_payment_settled",
                    "gameplay.economy.commerce_delivery_payment_compensated",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.commerce_delivery_payment_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:survival-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.survival_domain",
                stream_patterns=("gameplay:survival:{actor_ref}",),
                event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                    "gameplay.survival.state_expired",
                    "gameplay.survival.obligation_settled",
                    "gameplay.survival.state_dispelled",
                    "gameplay.survival.state_transformed",
                    "gameplay.survival.obligation_cancelled",
                    "gameplay.survival.obligation_retry_scheduled",
                    "gameplay.survival.state_compensated",
                    "gameplay.survival.obligation_compensated",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ObligationSettlementCoordinator.replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-maintenance-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=(
                    "gameplay.construction_production.maintenance_state_applied",
                    "gameplay.construction_production.maintenance_state_obligation_opened",
                    "gameplay.construction_production.maintenance_state_expired",
                    "gameplay.construction_production.maintenance_state_obligation_settled",
                    "gameplay.construction_production.maintenance_state_dispelled",
                    "gameplay.construction_production.maintenance_state_obligation_cancelled",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:ecology-frost-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref="authority:ecology",
                stream_patterns=("gameplay:ecology:{region_ref}",),
                event_types=(
                    "gameplay.ecology.crop_state_applied",
                    "gameplay.ecology.crop_state_obligation_opened",
                    "gameplay.ecology.crop_state_expired",
                    "gameplay.ecology.crop_state_obligation_settled",
                    "gameplay.ecology.crop_state_dispelled",
                    "gameplay.ecology.crop_state_obligation_cancelled",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EcologyHazardAuthority.replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:ecology-drought-state-expiry@1",
                contract_kind="lifecycle",
                owner_ref="authority:ecology",
                stream_patterns=("gameplay:ecology:{region_ref}",),
                event_types=(
                    "gameplay.ecology.drought_state_applied",
                    "gameplay.ecology.drought_state_obligation_opened",
                    "gameplay.ecology.drought_state_expired",
                    "gameplay.ecology.drought_state_obligation_settled",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EcologyHazardAuthority.replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-wage-accrual-obligation@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.econ1_economy_domain",
                stream_patterns=("gameplay:economy:wage:{worker_ref}",),
                event_types=(
                    "gameplay.economy.wage_obligation_opened",
                    "gameplay.economy.wage_accrued",
                    "gameplay.economy.wage_obligation_settled",
                    "gameplay.economy.wage_obligation_retry_scheduled",
                    "gameplay.economy.wage_obligation_cancelled",
                    "gameplay.economy.wage_obligation_expired",
                    "gameplay.economy.wage_accrual_compensated",
                    "gameplay.economy.wage_obligation_compensated",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ObligationSettlementCoordinator.replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-tax-obligation@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=(
                    "gameplay.economy.tax_due_recorded",
                    "gameplay.economy.tax_obligation_opened",
                    "gameplay.economy.tax_obligation_settled",
                    "gameplay.economy.tax_obligation_cancelled",
                    "gameplay.economy.tax_obligation_expired",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ObligationSettlementCoordinator.replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-inspection-policy@1",
                contract_kind="policy",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:{organization_ref}",),
                event_types=(
                    "gameplay.government.commercial_inspection_policy_registered",
                    "gameplay.government.commercial_inspection_policy_revoked",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentAuthority.commercial_inspection_policy_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-failed-inspection-promotion@1",
                contract_kind="branch_promotion",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:{organization_ref}",),
                event_types=("gameplay.government.inspection_recorded",),
                projection_scope="project",
                receipt_reader_ref="GovernmentBranchPromotionReceipt",
                replay_reader_ref="BranchPreviewAuthority.production_replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-inspection-promotion@1",
                contract_kind="branch_promotion",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:{organization_ref}",),
                event_types=("gameplay.government.inspection_recorded",),
                projection_scope="project",
                receipt_reader_ref="GovernmentBranchPromotionReceipt",
                replay_reader_ref="BranchPreviewAuthority.production_replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-operating-window@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:window:{window_ref}",),
                event_types=(
                    "gameplay.organization.operating_window_opened",
                    "gameplay.organization.operating_window_closed",
                    "gameplay.organization.operating_window_due_recorded",
                ),
                projection_scope="mixed",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority._operating_window_state",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:simple-debt-settlement@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.debt_domain",
                stream_patterns=("gameplay:economy", "gameplay:contracts", "gameplay:debt", "gameplay:commerce"),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.contract.simple_debt_created",
                    "gameplay.contract.simple_debt_fulfilled",
                    "gameplay.contract.simple_debt_cancelled",
                    "gameplay.contract.simple_debt_reopened",
                    "gameplay.contract.simple_debt_cancellation_reversed",
                    "gameplay.debt.claim_issued",
                    "gameplay.debt.claim_overdue",
                    "gameplay.debt.claim_defaulted",
                    "gameplay.debt.payment_applied",
                    "gameplay.debt.payment_corrected",
                    "gameplay.debt.claim_satisfied",
                    "gameplay.debt.claim_cancelled",
                    "gameplay.debt.claim_reopened",
                    "gameplay.debt.claim_cancellation_reversed",
                    "gameplay.commerce.debt_issued_settled",
                    "gameplay.commerce.debt_payment_settled",
                    "gameplay.commerce.debt_cancelled_settled",
                    "gameplay.commerce.debt_payment_corrected_settled",
                    "gameplay.commerce.debt_cancellation_reversed",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="DebtAuthorityService.replay_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-construction-maintenance@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=(
                    "gameplay.construction_production.maintenance_obligation_created",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GameplayProjectionReplay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-economy-quote@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.dynamic_quote_published",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-economy-quote-fanout@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.dynamic_quote_published",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-survival-cold@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.survival_domain",
                stream_patterns=("gameplay:survival:{profile_ref}",),
                event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="SurvivalProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-survival-heat@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.survival_domain",
                stream_patterns=("gameplay:survival:{profile_ref}",),
                event_types=(
                    "gameplay.survival.state_applied",
                    "gameplay.survival.obligation_opened",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="SurvivalProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-scheduled-transfer-policy@1",
                contract_kind="policy",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=(
                    "gameplay.economy.scheduled_transfer_policy_registered",
                    "gameplay.economy.scheduled_transfer_policy_revoked",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-organization-supply@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.commerce_commitment_accepted",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.commerce_commitment_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-organization-supply-fanout@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.commerce_commitment_accepted",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.commerce_commitment_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-supply-promotion@1",
                contract_kind="branch_promotion",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.commerce_commitment_accepted",),
                projection_scope="project",
                receipt_reader_ref="OrganizationBranchPromotionReceipt",
                replay_reader_ref="OrganizationAuthority.commerce_commitment_projection",
            ),
        )
        return tuple(sorted(contracts, key=lambda contract: contract.contract_ref))

    @classmethod
    def require(
        cls, *, contract_ref: str, contract_kind: str | None = None
    ) -> GovernedAuthorityContract:
        for contract in cls.contracts():
            if contract.contract_ref != contract_ref:
                continue
            if contract_kind is not None and contract.contract_kind != contract_kind:
                raise GovernedAuthorityContractError("governed_authority_contract_kind_mismatch")
            return contract
        raise GovernedAuthorityContractError("governed_authority_contract_unknown")

    @classmethod
    def require_operation(
        cls,
        *,
        contract_ref: str,
        contract_kind: str,
        owner_ref: str,
        stream_ids: tuple[str, ...],
        event_types: tuple[str, ...],
        projection_scope: str,
    ) -> GovernedAuthorityContract:
        contract = cls.require(contract_ref=contract_ref, contract_kind=contract_kind)
        if contract.owner_ref != owner_ref or contract.projection_scope != projection_scope:
            raise GovernedAuthorityContractError("governed_authority_contract_owner_mismatch")
        if any(not cls._matches_stream_pattern(stream_id, contract.stream_patterns) for stream_id in stream_ids):
            raise GovernedAuthorityContractError("governed_authority_contract_stream_mismatch")
        if any(event_type not in contract.event_types for event_type in event_types):
            raise GovernedAuthorityContractError("governed_authority_contract_event_mismatch")
        return contract

    @staticmethod
    def _matches_stream_pattern(stream_id: str, patterns: tuple[str, ...]) -> bool:
        for pattern in patterns:
            # Existing identifiers may themselves contain colons (for example
            # `organization:policy-registration`), so a placeholder consumes
            # the remaining non-empty stream suffix rather than one segment.
            expression = re.sub(r"\\\{[^}]+\\\}", r".+", re.escape(pattern))
            if re.fullmatch(expression, stream_id):
                return True
        return False


__all__ = [
    "GovernedAuthorityContract",
    "GovernedAuthorityContractCatalog",
    "GovernedAuthorityContractError",
]
