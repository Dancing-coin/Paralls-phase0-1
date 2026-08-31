from __future__ import annotations

import re
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel


class GovernedAuthorityContractError(ValueError):
    pass


class GovernedAuthorityContract(StrictGameplayModel):
    """Read-only cross-INF admission metadata for an already-existing owner."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_ref: str = Field(min_length=1)
    contract_kind: Literal["lifecycle", "policy", "settlement", "ecology_consumer", "branch_promotion", "contract_admission"]
    owner_ref: str = Field(min_length=1)
    stream_patterns: tuple[str, ...] = Field(min_length=1)
    event_types: tuple[str, ...] = Field(min_length=1)
    projection_scope: Literal["project", "authority_only", "mixed", "actor_private"]
    receipt_reader_ref: str = Field(min_length=1)
    replay_reader_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_actor_private_scope(self) -> "GovernedAuthorityContract":
        if self.projection_scope != "actor_private":
            return self
        if (
            self.contract_kind != "contract_admission"
            or self.owner_ref != "authority:p5:social"
            or self.receipt_reader_ref != "GameplayEventStore.append_batch"
            or (
                self.contract_ref == "inf:social-handshake-shared-experience@1"
                and (
                    self.stream_patterns != ("gameplay:social:shared-experience:{participant_ref}",)
                    or self.event_types != ("gameplay.social.handshake_shared_experience_recorded",)
                    or self.replay_reader_ref != "SocialFactAuthority.handshake_shared_experience_view_for"
                )
            )
            or (
                self.contract_ref == "inf:social-public-milling-notice-acknowledgment@1"
                and (
                    self.stream_patterns != (
                        "gameplay:social:public-milling-notice-acknowledgment:{participant_ref}",
                    )
                    or self.event_types != ("gameplay.social.public_milling_notice_acknowledged",)
                    or self.replay_reader_ref
                    != "SocialFactAuthority.public_milling_notice_social_acknowledgment_view_for"
                )
            )
            or (
                self.contract_ref == "inf:private-follow-on@1"
                and (
                    self.stream_patterns != ("gameplay:social:public-milling-notice-acknowledgment:{participant_ref}",)
                    or self.event_types != ("gameplay.social.public_milling_notice_acknowledged",)
                    or self.replay_reader_ref != "SocialFactAuthority.public_milling_notice_social_acknowledgment_view_for"
                )
            )
            or self.contract_ref
            not in {
                "inf:social-handshake-shared-experience@1",
                "inf:social-public-milling-notice-acknowledgment@1",
                "inf:private-follow-on@1",
            }
        ):
            raise ValueError("governed_actor_private_scope_unadmitted")
        return self


class OwnerOperationDescriptor(StrictGameplayModel):
    """Frozen metadata for one separately admitted owner operation family."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    descriptor_ref: str = Field(min_length=1)
    family_ref: str | None = None
    descriptor_revision: str = Field(min_length=1)
    capability_ref: str = Field(min_length=1)
    outcome_family_ref: str = Field(min_length=1)
    allowed_predicate_family_refs: tuple[str, ...] = ()
    allowed_proposal_effect_types: tuple[str, ...] = ()
    # Optional family metadata. Existing narrow descriptors intentionally keep
    # these empty; closed families populate every authority-owned coordinate.
    owner_ref: str | None = None
    accepted_intent_schema_ref: str | None = None
    source_event_types: tuple[str, ...] = ()
    source_stream_pattern: str | None = None
    source_revision_fence_ref: str | None = None
    target_stream_pattern: str | None = None
    target_event_types: tuple[str, ...] = ()
    privacy_scope: Literal["project", "authority_only", "mixed", "actor_private"] | None = None
    idempotency_rule_ref: str | None = None
    receipt_reader_ref: str | None = None
    replay_reader_refs: tuple[str, ...] = ()
    terminal_semantics_ref: str | None = None
    reversal_semantics_ref: str | None = None
    compensation_semantics_ref: str | None = None
    allowed_recipe_family_refs: tuple[str, ...] = ()
    package_slot_refs: tuple[str, ...] = ()

    def model_post_init(self, __context: object) -> None:
        if not self.descriptor_ref.startswith("descriptor:") or "@" not in self.descriptor_ref:
            raise ValueError("owner_operation_descriptor_invalid")
        if not self.descriptor_revision.startswith("descriptor:") or "@" not in self.descriptor_revision:
            raise ValueError("owner_operation_descriptor_invalid")
        if not self.capability_ref.startswith("capability:") or "@" not in self.capability_ref:
            raise ValueError("owner_operation_descriptor_invalid")
        if not self.outcome_family_ref.startswith("outcome:") or "@" not in self.outcome_family_ref:
            raise ValueError("owner_operation_descriptor_invalid")
        if (
            len(set(self.allowed_predicate_family_refs)) != len(self.allowed_predicate_family_refs)
            or tuple(sorted(self.allowed_predicate_family_refs)) != self.allowed_predicate_family_refs
            or any(not value.startswith("predicate:") or "@" not in value for value in self.allowed_predicate_family_refs)
        ):
            raise ValueError("owner_operation_descriptor_invalid")
        if (
            len(set(self.allowed_proposal_effect_types)) != len(self.allowed_proposal_effect_types)
            or tuple(sorted(self.allowed_proposal_effect_types)) != self.allowed_proposal_effect_types
            or any(not value.startswith("effect:") or "@" not in value for value in self.allowed_proposal_effect_types)
        ):
            raise ValueError("owner_operation_descriptor_invalid")
        if self.owner_ref is not None and not self.owner_ref:
            raise ValueError("owner_operation_descriptor_invalid")
        for value in (
            self.accepted_intent_schema_ref,
            self.source_revision_fence_ref,
            self.idempotency_rule_ref,
            self.terminal_semantics_ref,
            self.reversal_semantics_ref,
            self.compensation_semantics_ref,
        ):
            if value is not None and (":" not in value or "@" not in value):
                raise ValueError("owner_operation_descriptor_invalid")
        if self.receipt_reader_ref is not None and not self.receipt_reader_ref:
            raise ValueError("owner_operation_descriptor_invalid")
        for value in (self.source_stream_pattern, self.target_stream_pattern):
            if value is not None and not value.startswith("gameplay:"):
                raise ValueError("owner_operation_descriptor_invalid")
        for values in (self.source_event_types, self.target_event_types, self.replay_reader_refs):
            if len(set(values)) != len(values) or tuple(sorted(values)) != values:
                raise ValueError("owner_operation_descriptor_invalid")
        if any(not value.startswith(("reader:", "gameplay.")) for value in self.replay_reader_refs):
            raise ValueError("owner_operation_descriptor_invalid")
        if len(set(self.allowed_recipe_family_refs)) != len(self.allowed_recipe_family_refs):
            raise ValueError("owner_operation_descriptor_invalid")
        if any("@" not in value for value in self.allowed_recipe_family_refs):
            raise ValueError("owner_operation_descriptor_invalid")
        if len(set(self.package_slot_refs)) != len(self.package_slot_refs):
            raise ValueError("owner_operation_descriptor_invalid")
        if any(not value.startswith("slot:") or "@" not in value for value in self.package_slot_refs):
            raise ValueError("owner_operation_descriptor_invalid")


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
                contract_ref="inf:economy-government-tax-payment@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=(
                    "gameplay.economy.tax_obligation_payer_bound",
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.tax_payment_settled",
                    "gameplay.economy.tax_obligation_settled",
                    "gameplay.economy.tax_payment_reversal_requested",
                    "gameplay.economy.tax_payment_compensated",
                    "gameplay.economy.tax_obligation_reopened",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.tax_payment_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:package-declared-negotiated-exchange@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=(
                    "gameplay:economy",
                    "gameplay:inventory:{actor_ref}",
                    "gameplay:ownership",
                    "gameplay:contracts",
                ),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.package_declared_negotiated_exchange_settled",
                    "gameplay.inventory.item_transferred_out",
                    "gameplay.inventory.item_transferred_in",
                    "gameplay.ownership.right_transferred",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.package_declared_negotiated_exchange_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:industrial-facility-reinforced-mill-flour-output-purchase@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=(
                    "gameplay:economy",
                    "gameplay:inventory:organization:district-milling-cooperative",
                    "gameplay:inventory:{actor_ref}",
                    "gameplay:construction_production:{facility_ref}",
                ),
                event_types=(
                    "gameplay.economy.account_debited",
                    "gameplay.economy.account_credited",
                    "gameplay.economy.package_declared_negotiated_exchange_settled",
                    "gameplay.inventory.mill_flour_output_received@1",
                    "gameplay.inventory.item_transferred_out",
                    "gameplay.inventory.item_transferred_in",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.package_declared_negotiated_exchange_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-treasury-collector@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.government_treasury_collector",
                stream_patterns=("gameplay:government_treasury:{jurisdiction_ref}",),
                event_types=("gameplay.government_treasury.collector_account_admitted",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentTreasuryCollectorAuthority.collector_identity_projection",
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
                contract_ref="inf:construction-facility-bakery-reinforcement@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_transformed",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-package-declared-transform@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_transformed",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-recipe-production@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=(
                    "gameplay.construction_production.run_started",
                    "gameplay.construction_production.run_finished",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-mill-reinforcement@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_transformed",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-mill-decommission@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_decommissioned",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-operational-verification@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_operationally_verified",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-public-use-enable@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_public_use_enabled",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-mill-reinforced-public-use@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.facility_public_use_enabled",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-reinforced-mill-flour-output-certification@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.mill_flour_output_certified@1",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-public-project-step-completion@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=("gameplay.construction_production.public_project_step_completed",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ConstructionProductionAuthority.projector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:construction-facility-repair@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.construction_production_domain",
                stream_patterns=("gameplay:construction_production:{facility_ref}",),
                event_types=(
                    "gameplay.construction_production.facility_repaired",
                    "gameplay.construction_production.facility_repair_compensated",
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
                contract_ref="inf:ecology-weather-rain-crop-recovery@1",
                contract_kind="ecology_consumer",
                owner_ref="authority:ecology",
                stream_patterns=("gameplay:ecology:{region_ref}",),
                event_types=("gameplay.ecology.crop.recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EcologyHazardAuthority.regional_replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:ecology-weather-rain-water-resource-recovery@1",
                contract_kind="ecology_consumer",
                owner_ref="authority:ecology",
                stream_patterns=("gameplay:ecology:{region_ref}",),
                event_types=("gameplay.ecology.resource.recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EcologyHazardAuthority.regional_replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:ecology-grain-harvest@1",
                contract_kind="ecology_consumer",
                owner_ref="authority:ecology",
                stream_patterns=("gameplay:ecology:{region_ref}",),
                event_types=(
                    "gameplay.ecology.grain_crop.admitted",
                    "gameplay.ecology.grain_harvested",
                ),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EcologyHazardAuthority.regional_replay",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:inventory-grain-harvest-custody@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.inventory_domain",
                stream_patterns=("gameplay:inventory:{actor_ref}",),
                event_types=("gameplay.inventory.grain_harvest_received@1",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="InventoryProjector.rebuild",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-grain-intake@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.grain_intake_recorded@1",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.grain_intake_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-grain-intake-acceptance@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.grain_intake_accepted@1",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.grain_intake_acceptance_projection",
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
                contract_ref="inf:branch-work-wage-admission@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.econ1_economy_domain",
                stream_patterns=("gameplay:economy:wage:{worker_ref}",),
                event_types=("gameplay.economy.wage_accrued",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthority.settle_production_evidence_wage_accrual",
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
                contract_ref="inf:organization-production-work-contribution-acceptance@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.production_work_contribution_accepted",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.work_contribution_acceptance_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-production-work-order-fulfillment@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.work_order_fulfilled",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.work_order_fulfillment_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-public-project-budget-commitment@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.public_project_budget_commitment_recorded",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.public_project_budget_commitment_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-public-project-budget-reservation@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.budget_reserved",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.public_project_budget_reservation_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-public-project-budget-consumption@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.public_project_budget_consumed",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.public_project_budget_consumption_projection",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:economy-public-project-budget-close@1",
                contract_kind="lifecycle",
                owner_ref="actor_gameplay.economy_domain",
                stream_patterns=("gameplay:economy",),
                event_types=("gameplay.economy.public_project_budget_closed",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="EconomyAuthorityService.public_project_budget_close_projection",
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
                contract_ref="inf:weather-front-survival-dehydration@1",
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
                contract_ref="inf:weather-front-survival-hydration@1",
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
            GovernedAuthorityContract(
                contract_ref="inf:weather-front-government-drought-advisory@1",
                contract_kind="ecology_consumer",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:advisory:{jurisdiction_ref}",),
                event_types=("gameplay.government.drought_advisory_issued",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentAuthority.drought_advisory_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:ownership-certificate-government-drought-assessment-acknowledgment@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:advisory:{jurisdiction_ref}",),
                event_types=("gameplay.government.drought_assessment_acknowledged",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentAuthority.drought_assessment_acknowledgment_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-drought-advisory-municipal-assessment-contract@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:municipal-drought-assessment-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=(
                    "gameplay.contract.service_completion_recorded",
                    "gameplay.contract.record_fulfilled",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:facility-commissioning-review-contract-admission@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:facility-commissioning-review-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=(
                    "gameplay.contract.service_completion_recorded",
                    "gameplay.contract.record_fulfilled",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:public-workshop-session-contract-admission@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:industrial-facility-public-milling-session-contract-admission@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=("gameplay.contract.record_created",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:industrial-facility-public-milling-session-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=("gameplay.contract.service_completion_recorded", "gameplay.contract.record_fulfilled"),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:public-workshop-session-contract-fulfillment@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.contract_domain",
                stream_patterns=("gameplay:contracts",),
                event_types=(
                    "gameplay.contract.service_completion_recorded",
                    "gameplay.contract.record_fulfilled",
                ),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="ContractProjector",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-public-workshop-activity@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.public_workshop_activity_recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.public_workshop_activity_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-public-milling-activity@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.public_milling_activity_recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.public_milling_activity_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:organization-public-project-execution@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.organization_domain",
                stream_patterns=("gameplay:organization:{organization_ref}",),
                event_types=("gameplay.organization.public_project_execution_recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OrganizationAuthority.public_project_execution_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-public-workshop-notice@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:public-notice:{jurisdiction_ref}",),
                event_types=("gameplay.government.public_workshop_notice_recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentAuthority.public_workshop_notice_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-public-milling-notice@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:public-notice:{jurisdiction_ref}",),
                event_types=("gameplay.government.public_milling_notice_recorded",),
                projection_scope="project",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentAuthority.public_milling_notice_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:government-public-project-execution-acknowledgment@1",
                contract_kind="contract_admission",
                owner_ref="actor_gameplay.government_domain",
                stream_patterns=("gameplay:government:public-project:{jurisdiction_ref}",),
                event_types=("gameplay.government.public_project_execution_acknowledged",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="GovernmentAuthority.public_project_execution_acknowledgment_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:social-handshake-shared-experience@1",
                contract_kind="contract_admission",
                owner_ref="authority:p5:social",
                stream_patterns=("gameplay:social:shared-experience:{participant_ref}",),
                event_types=("gameplay.social.handshake_shared_experience_recorded",),
                projection_scope="actor_private",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="SocialFactAuthority.handshake_shared_experience_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:social-public-milling-notice-acknowledgment@1",
                contract_kind="contract_admission",
                owner_ref="authority:p5:social",
                stream_patterns=(
                    "gameplay:social:public-milling-notice-acknowledgment:{participant_ref}",
                ),
                event_types=("gameplay.social.public_milling_notice_acknowledged",),
                projection_scope="actor_private",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="SocialFactAuthority.public_milling_notice_social_acknowledgment_view_for",
            ),
            GovernedAuthorityContract(
                contract_ref="inf:contract-completed-municipal-drought-assessment-certificate@1",
                contract_kind="settlement",
                owner_ref="actor_gameplay.ownership_domain",
                stream_patterns=("gameplay:ownership",),
                event_types=("gameplay.ownership.right_granted",),
                projection_scope="authority_only",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref="OwnershipProjector",
            ),
        )
        return tuple(sorted(contracts, key=lambda contract: contract.contract_ref))

    @staticmethod
    def descriptors() -> tuple[OwnerOperationDescriptor, ...]:
        """Return only statically admitted operation descriptors.

        Rows are source-defined and immutable. There is no registration or
        mutation API.
        """
        return (
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
                descriptor_ref="descriptor:construction-recipe-production@1",
                descriptor_revision="descriptor:construction-recipe-production@1",
                family_ref="recipe_production@1",
                capability_ref="capability:recipe-production@1",
                outcome_family_ref="outcome:recipe-production@1",
                allowed_predicate_family_refs=("predicate:construction-facility-committed@1",),
                allowed_proposal_effect_types=("effect:recipe-production-run@1",),
                owner_ref="actor_gameplay.construction_production_domain",
                accepted_intent_schema_ref="schema:construction-recipe-production-intent@1",
                source_event_types=("gameplay.construction_production.facility_acquired",),
                source_stream_pattern="gameplay:construction_production:{facility_ref}",
                source_revision_fence_ref="revision:construction-source-and-facility-head@1",
                target_stream_pattern="gameplay:construction_production:{facility_ref}",
                target_event_types=(
                    "gameplay.construction_production.run_finished",
                    "gameplay.construction_production.run_started",
                ),
                privacy_scope="project",
                idempotency_rule_ref="idempotency:construction-recipe-production@1",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_refs=(
                    "reader:construction-production-checkpoint-tail@1",
                    "reader:construction-production-full@1",
                ),
                terminal_semantics_ref="lifecycle:terminal-no-compensation@1",
                reversal_semantics_ref="lifecycle:none@1",
                compensation_semantics_ref="lifecycle:none@1",
                allowed_recipe_family_refs=("recipe_production@1",),
                package_slot_refs=(
                    "slot:duration@1",
                    "slot:facility-definition@1",
                    "slot:input-items@1",
                    "slot:output-items@1",
                    "slot:qualification@1",
                    "slot:recipe-definition@1",
                ),
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
                descriptor_ref="descriptor:construction-reinforced-mill-flour-output-certification@1",
                descriptor_revision="descriptor:construction-reinforced-mill-flour-output-certification@1",
                capability_ref="capability:construction-reinforced-mill-flour-output-certification@1",
                outcome_family_ref="outcome:construction-reinforced-mill-flour-output-certified@1",
                allowed_predicate_family_refs=("predicate:construction-reinforced-mill-flour-output-certifiable@1",),
                allowed_proposal_effect_types=("effect:construction-reinforced-mill-flour-output-certification@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:industrial-facility-reinforced-mill-flour-output-purchase@1",
                descriptor_revision="descriptor:industrial-facility-reinforced-mill-flour-output-purchase@1",
                capability_ref="capability:package-declared-negotiated-exchange@1",
                outcome_family_ref="outcome:industrial-facility-reinforced-mill-flour-output-purchase@1",
                allowed_predicate_family_refs=(
                    "predicate:construction-reinforced-mill-flour-output-certified@1",
                ),
                allowed_proposal_effect_types=(
                    "effect:industrial-facility-reinforced-mill-flour-output-purchase@1",
                ),
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
                descriptor_ref="descriptor:industrial-facility-public-milling-session-contract-admission@1",
                descriptor_revision="descriptor:industrial-facility-public-milling-session-contract-admission@1",
                capability_ref="capability:industrial-facility-public-milling-session@1",
                outcome_family_ref="outcome:industrial-facility-public-milling-session-contract@1",
                allowed_predicate_family_refs=("predicate:construction-facility-mill-reinforced-public-use-enabled@1",),
                allowed_proposal_effect_types=("effect:industrial-facility-public-milling-session-contract-created@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:industrial-facility-public-milling-session-contract-fulfillment@1",
                descriptor_revision="descriptor:industrial-facility-public-milling-session-contract-fulfillment@1",
                capability_ref="capability:industrial-facility-public-milling-session@1",
                outcome_family_ref="outcome:industrial-facility-public-milling-session-fulfilled@1",
                allowed_predicate_family_refs=("predicate:industrial-facility-public-milling-session-active@1",),
                allowed_proposal_effect_types=("effect:industrial-facility-public-milling-session-fulfilled@1",),
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
                descriptor_ref="descriptor:organization-public-milling-activity@1",
                descriptor_revision="descriptor:organization-public-milling-activity@1",
                capability_ref="capability:organization-public-milling-activity@1",
                outcome_family_ref="outcome:organization-public-milling-activity-recorded@1",
                allowed_predicate_family_refs=("predicate:contract-public-milling-session-fulfilled@1",),
                allowed_proposal_effect_types=("effect:organization-public-milling-activity-recorded@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:organization-public-project-execution@1",
                descriptor_revision="descriptor:organization-public-project-execution@1",
                capability_ref="capability:organization-public-project-execution@1",
                outcome_family_ref="outcome:organization-public-project-execution-recorded@1",
                allowed_predicate_family_refs=(
                    "predicate:economy-public-project-budget-consumed-and-workshop-activity@1",
                ),
                allowed_proposal_effect_types=(
                    "effect:organization-public-project-execution-recorded@1",
                ),
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
                descriptor_ref="descriptor:government-public-milling-notice@1",
                descriptor_revision="descriptor:government-public-milling-notice@1",
                capability_ref="capability:government-public-milling-notice@1",
                outcome_family_ref="outcome:government-public-milling-notice-recorded@1",
                allowed_predicate_family_refs=("predicate:organization-public-milling-activity-completed@1",),
                allowed_proposal_effect_types=("effect:government-public-milling-notice-recorded@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:government-public-project-execution-acknowledgment@1",
                descriptor_revision="descriptor:government-public-project-execution-acknowledgment@1",
                capability_ref="capability:government-public-project-execution-acknowledgment@1",
                outcome_family_ref="outcome:government-public-project-execution-acknowledged@1",
                allowed_predicate_family_refs=("predicate:organization-public-project-funded-and-executed@1",),
                allowed_proposal_effect_types=("effect:government-public-project-execution-acknowledged@1",),
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
                descriptor_ref="descriptor:social-public-milling-notice-acknowledgment@1",
                descriptor_revision="descriptor:social-public-milling-notice-acknowledgment@1",
                capability_ref="capability:social-public-milling-notice-acknowledgment@1",
                outcome_family_ref="outcome:social-public-milling-notice-acknowledged@1",
                allowed_predicate_family_refs=("predicate:government-public-milling-notice-recorded@1",),
                allowed_proposal_effect_types=("effect:social-public-milling-notice-acknowledged@1",),
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
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:ecology-weather-rain-crop-recovery@1",
                descriptor_revision="descriptor:ecology-weather-rain-crop-recovery@1",
                capability_ref="capability:ecology-weather-rain-crop-recovery@1",
                outcome_family_ref="outcome:ecology-weather-rain-crop-recovered@1",
                allowed_predicate_family_refs=("predicate:ecology-weather-front-rain-and-crop-damaged@1",),
                allowed_proposal_effect_types=("effect:ecology-weather-rain-crop-recovered@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:ecology-weather-rain-water-resource-recovery@1",
                descriptor_revision="descriptor:ecology-weather-rain-water-resource-recovery@1",
                capability_ref="capability:ecology-weather-rain-water-resource-recovery@1",
                outcome_family_ref="outcome:ecology-weather-rain-water-resource-recovered@1",
                allowed_predicate_family_refs=("predicate:ecology-weather-front-rain-and-water-resource@1",),
                allowed_proposal_effect_types=("effect:ecology-weather-rain-water-resource-recovered@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:ecology-grain-harvest@1",
                descriptor_revision="descriptor:ecology-grain-harvest@1",
                capability_ref="capability:ecology-grain-harvest@1",
                outcome_family_ref="outcome:ecology-grain-harvested@1",
                allowed_predicate_family_refs=("predicate:ecology-mature-grain-crop@1",),
                allowed_proposal_effect_types=("effect:ecology-grain-harvested@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:inventory-grain-harvest-custody@1",
                descriptor_revision="descriptor:inventory-grain-harvest-custody@1",
                capability_ref="capability:inventory-grain-harvest-custody@1",
                outcome_family_ref="outcome:inventory-grain-harvest-custody-recorded@1",
                allowed_predicate_family_refs=("predicate:ecology-grain-harvested@1",),
                allowed_proposal_effect_types=("effect:inventory-grain-harvest-custody-recorded@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:organization-grain-intake@1",
                descriptor_revision="descriptor:organization-grain-intake@1",
                capability_ref="capability:organization-grain-intake@1",
                outcome_family_ref="outcome:organization-grain-intake-recorded@1",
                allowed_predicate_family_refs=("predicate:inventory-grain-harvest-custody@1",),
                allowed_proposal_effect_types=("effect:organization-grain-intake-recorded@1",),
            ),
            OwnerOperationDescriptor(
                descriptor_ref="descriptor:economy-grain-intake-acceptance@1",
                descriptor_revision="descriptor:economy-grain-intake-acceptance@1",
                capability_ref="capability:economy-grain-intake-acceptance@1",
                outcome_family_ref="outcome:economy-grain-intake-accepted@1",
                allowed_predicate_family_refs=("predicate:organization-grain-intake-recorded@1",),
                allowed_proposal_effect_types=("effect:economy-grain-intake-accepted@1",),
            ),
        )

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
        for contract in cls.closed_family_contracts():
            if contract.contract_ref != contract_ref:
                continue
            if contract_kind is not None and contract.contract_kind != contract_kind:
                raise GovernedAuthorityContractError("governed_authority_contract_kind_mismatch")
            return contract
        raise GovernedAuthorityContractError("governed_authority_contract_unknown")

    @staticmethod
    def closed_family_contracts() -> tuple[GovernedAuthorityContract, ...]:
        """Read-only rows for the closed generic family vocabulary."""
        from app.gameplay.closed_generic_gameplay_families import CLOSED_GAMEPLAY_FAMILIES
        replay_readers = {
            "recipe_production@1": "ConstructionProductionAuthority.projector",
            "facility_identity_upgrade@1": "ConstructionProductionAuthority.projector",
            "facility_lifecycle_transition@1": "ConstructionProductionAuthority.projector",
            "production_output_certification@1": "ConstructionProductionAuthority.projector",
            "production_output_custody@1": "InventoryProjector.rebuild",
            "declared_exchange@1": "EconomyAuthorityService.declared_exchange_projection",
            "fixed_service_exchange@1": "EconomyAuthorityService.package_declared_negotiated_exchange_projection",
            "bounded_project_budget@1": "EconomyAuthorityService.public_project_budget_commitment_projection",
            "harvest_to_custody@1": "InventoryAuthorityService.harvest_to_custody_view_for",
            "owner_bound_environment_consumer@1": "SurvivalAuthority.projector",
            "domain_acceptance_marker@1": "OrganizationAuthority.domain_acceptance_marker_view_for",
            "private_follow_on@1": "SocialFactAuthority.public_milling_notice_social_acknowledgment_view_for",
        }

        return tuple(
            GovernedAuthorityContract(
                contract_ref=family.contract_ref,
                contract_kind=family.contract_kind,
                owner_ref=family.owner_ref,
                stream_patterns=(family.stream_pattern,),
                event_types=family.event_types,
                projection_scope=family.privacy_scope,
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_ref=replay_readers[family.family_ref],
            )
            for family in CLOSED_GAMEPLAY_FAMILIES
        )

    @classmethod
    def all_descriptors(cls) -> tuple[OwnerOperationDescriptor, ...]:
        """Existing descriptors plus closed-family descriptors, read-only."""
        from app.gameplay.closed_generic_gameplay_families import CLOSED_GAMEPLAY_FAMILIES

        existing = cls.descriptors()
        known = {item.descriptor_ref for item in existing}
        family_descriptors = tuple(
            OwnerOperationDescriptor(
                descriptor_ref=family.descriptor_ref,
                descriptor_revision=family.descriptor_ref,
                family_ref=family.family_ref,
                capability_ref=family.capability_ref,
                outcome_family_ref=family.outcome_family_ref,
                allowed_predicate_family_refs=family.predicate_family_refs,
                allowed_proposal_effect_types=family.effect_types,
                owner_ref=family.owner_ref,
                accepted_intent_schema_ref=f"schema:{family.family_ref.replace('@', '-')}-intent@1",
                source_event_types=family.event_types[:1],
                source_stream_pattern=family.stream_pattern,
                source_revision_fence_ref=f"revision:{family.family_ref.replace('@', '-')}-source@1",
                target_stream_pattern=family.stream_pattern,
                target_event_types=tuple(sorted(family.event_types)),
                privacy_scope=family.privacy_scope,
                idempotency_rule_ref=f"idempotency:{family.family_ref.replace('@', '-') }@1",
                receipt_reader_ref="GameplayEventStore.append_batch",
                replay_reader_refs=(
                    f"reader:{family.family_ref.replace('@', '-')}-checkpoint-tail@1",
                    f"reader:{family.family_ref.replace('@', '-')}-full@1",
                ),
                terminal_semantics_ref="lifecycle:terminal-no-compensation@1",
                reversal_semantics_ref="lifecycle:none@1",
                compensation_semantics_ref="lifecycle:none@1",
                allowed_recipe_family_refs=(family.family_ref,),
                package_slot_refs=family.package_slot_refs,
            )
            for family in CLOSED_GAMEPLAY_FAMILIES
            if family.descriptor_ref not in known and family.family_ref != "recipe_production@1"
        )
        return (*existing, *family_descriptors)

    @classmethod
    def require_descriptor(cls, descriptor_ref: str) -> OwnerOperationDescriptor:
        matches = tuple(item for item in cls.all_descriptors() if item.descriptor_ref == descriptor_ref)
        if not matches:
            raise GovernedAuthorityContractError("owner_operation_descriptor_unknown")
        if len(matches) != 1:
            raise GovernedAuthorityContractError("owner_operation_descriptor_ambiguous")
        return matches[0]

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
    "OwnerOperationDescriptor",
]
