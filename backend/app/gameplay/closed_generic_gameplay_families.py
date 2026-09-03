"""Closed gameplay-family contracts.

This module is deliberately declarative.  It defines the finite family
vocabulary and validates package content slots; it never selects an owner,
builds a fragment, or appends an event.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Type

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel
from app.gameplay.patch_runtime import _canonical_digest, _require_author_canonical, _require_platform_ref, _validate_platform_content


class ClosedFamilyContent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def reject_authority_coordinates(cls, value: object) -> object:
        _validate_platform_content(value)
        return value


class FacilityIdentityUpgradeContent(ClosedFamilyContent):
    source_definition_ref: str = Field(min_length=1)
    target_definition_ref: str = Field(min_length=1)
    source_kind: str = Field(min_length=1)
    target_kind: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)
    qualification_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_slots(self) -> "FacilityIdentityUpgradeContent":
        _require_platform_ref(self.source_definition_ref, prefix="definition:")
        _require_platform_ref(self.target_definition_ref, prefix="definition:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        _require_author_canonical(self.qualification_refs, identity=lambda value: value)
        return self


class FacilityLifecycleTransitionContent(ClosedFamilyContent):
    facility_definition_ref: str = Field(min_length=1)
    facility_kind: str = Field(min_length=1)
    from_lifecycle: str = Field(min_length=1)
    to_lifecycle: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)
    compensation_mode: Literal["none"] = "none"

    @model_validator(mode="after")
    def validate_slots(self) -> "FacilityLifecycleTransitionContent":
        _require_platform_ref(self.facility_definition_ref, prefix="definition:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        if self.from_lifecycle == self.to_lifecycle:
            raise ValueError("facility_lifecycle_transition_noop")
        return self


class FacilityIdentityUpgradeIntent(StrictGameplayModel):
    """Typed evidence request; family authority coordinates are not caller input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facility_ref: str = Field(min_length=1)
    acquisition_event_id: str = Field(min_length=1)
    expected_stream_revision: int = Field(ge=0)
    expected_facility_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class FacilityLifecycleTransitionIntent(StrictGameplayModel):
    """Typed lifecycle evidence request with no caller-selected transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    facility_ref: str = Field(min_length=1)
    acquisition_event_id: str = Field(min_length=1)
    expected_stream_revision: int = Field(ge=0)
    expected_facility_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class ProductionOutputCertificationContent(ClosedFamilyContent):
    recipe_ref: str = Field(min_length=1)
    output_item_definition_ref: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    policy_revision_ref: str = Field(min_length=1)
    quality_policy_revision_ref: str | None = None
    minimum_quality: float | None = Field(default=None, ge=0, le=1)
    maximum_quality: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "ProductionOutputCertificationContent":
        _require_platform_ref(self.recipe_ref, prefix="recipe:")
        _require_platform_ref(self.output_item_definition_ref, prefix="item:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        if self.quality_policy_revision_ref is not None:
            _require_platform_ref(self.quality_policy_revision_ref, prefix="policy:")
            if self.minimum_quality is None or self.maximum_quality is None or self.minimum_quality > self.maximum_quality:
                raise ValueError("production_output_certification_quality_policy_invalid")
        elif self.minimum_quality is not None or self.maximum_quality is not None:
            raise ValueError("production_output_certification_quality_policy_invalid")
        return self


class ProductionOutputCertificationIntent(StrictGameplayModel):
    """Committed run evidence request; output coordinates are package-bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_finished_event_id: str = Field(min_length=1)
    expected_run_finished_revision: int = Field(ge=1)
    expected_stream_revision: int = Field(ge=1)
    expected_facility_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class ProductionOutputCustodyContent(ClosedFamilyContent):
    output_item_definition_ref: str = Field(min_length=1)
    holder_binding_ref: str = Field(min_length=1)
    container_binding_ref: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "ProductionOutputCustodyContent":
        _require_platform_ref(self.output_item_definition_ref, prefix="item:")
        _require_platform_ref(self.holder_binding_ref, prefix="binding:")
        _require_platform_ref(self.container_binding_ref, prefix="binding:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        return self


class ProductionOutputCustodyIntent(StrictGameplayModel):
    """Certified-output request; Inventory derives all custody coordinates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    certification_event_id: str = Field(min_length=1)
    expected_certification_revision: int = Field(ge=1)
    expected_inventory_stream_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class DeclaredExchangeContent(ClosedFamilyContent):
    outcome_ref: str = Field(min_length=1)
    tradeable_definition_ref: str | None = None
    service_definition_ref: str | None = None
    policy_revision_ref: str = Field(min_length=1)
    eligibility_refs: tuple[str, ...]

    @model_validator(mode="after")
    def validate_slots(self) -> "DeclaredExchangeContent":
        _require_platform_ref(self.outcome_ref, prefix="outcome:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        if (self.tradeable_definition_ref is None) == (self.service_definition_ref is None):
            raise ValueError("declared_exchange_content_shape_invalid")
        if self.tradeable_definition_ref is not None:
            _require_platform_ref(self.tradeable_definition_ref, prefix="definition:")
        if self.service_definition_ref is not None:
            _require_platform_ref(self.service_definition_ref, prefix="definition:")
        _require_author_canonical(self.eligibility_refs, identity=lambda value: value)
        return self


class DeclaredExchangeIntent(StrictGameplayModel):
    """Committed custody source request; Economy derives every settlement coordinate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_id: str = Field(min_length=1)
    expected_source_revision: int = Field(ge=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class FixedServiceExchangeContent(ClosedFamilyContent):
    service_definition_ref: str = Field(min_length=1)
    service_ref: str = Field(min_length=1)
    outcome_ref: str = Field(min_length=1)
    provider_rule_ref: str = Field(min_length=1)
    receiver_rule_ref: str = Field(min_length=1)
    price_policy_ref: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "FixedServiceExchangeContent":
        _require_platform_ref(self.service_definition_ref, prefix="definition:")
        _require_platform_ref(self.service_ref, prefix="service:")
        _require_platform_ref(self.outcome_ref, prefix="outcome:")
        _require_platform_ref(self.provider_rule_ref, prefix="rule:")
        _require_platform_ref(self.receiver_rule_ref, prefix="rule:")
        _require_platform_ref(self.price_policy_ref, prefix="policy:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        return self


class FixedServiceExchangeIntent(StrictGameplayModel):
    """Closed service-settlement request; parties and price are owner-derived."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_digest: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class BoundedProjectBudgetContent(ClosedFamilyContent):
    project_definition_ref: str = Field(min_length=1)
    currency_ref: str = Field(min_length=1)
    amount: int = Field(gt=0)
    policy_revision_ref: str = Field(min_length=1)
    source_work_order_ref: str = Field(min_length=1)
    source_project_step_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "BoundedProjectBudgetContent":
        _require_platform_ref(self.project_definition_ref, prefix="definition:")
        if not self.currency_ref.startswith("currency:") or not self.currency_ref.removeprefix("currency:"):
            raise ValueError("platform_reference_invalid")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        _require_platform_ref(self.source_work_order_ref, prefix="work-order:")
        _require_platform_ref(self.source_project_step_ref, prefix="project-step:")
        return self


class BoundedProjectBudgetProjectStepIntent(StrictGameplayModel):
    """Construction source request; package content selects the source shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_id: str = Field(min_length=1)
    expected_source_revision: int = Field(ge=1)
    expected_target_stream_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


# The longer name is retained as a discoverable alias for callers that model
# the Construction side of the family explicitly.
BoundedProjectBudgetConstructionIntent = BoundedProjectBudgetProjectStepIntent


class BoundedProjectBudgetIntent(StrictGameplayModel):
    """Project-step source request; Economy derives amount/currency/lifecycle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class BoundedProjectBudgetReservationIntent(StrictGameplayModel):
    """Reservation evidence request; Economy derives account and amount."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commitment_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class BoundedProjectBudgetConsumptionIntent(StrictGameplayModel):
    """Consumption evidence request; Economy derives project and currency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    commitment_event_id: str = Field(min_length=1)
    reservation_event_id: str = Field(min_length=1)
    activity_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class BoundedProjectBudgetCloseIntent(StrictGameplayModel):
    """Close evidence request; Economy derives the terminal project binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget_consumed_event_id: str = Field(min_length=1)
    execution_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    causation_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)


class HarvestToCustodyContent(ClosedFamilyContent):
    crop_definition_ref: str = Field(min_length=1)
    item_definition_ref: str = Field(min_length=1)
    holder_binding_ref: str = Field(min_length=1)
    container_binding_ref: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "HarvestToCustodyContent":
        _require_platform_ref(self.crop_definition_ref, prefix="definition:")
        _require_platform_ref(self.item_definition_ref, prefix="item:")
        _require_platform_ref(self.holder_binding_ref, prefix="binding:")
        _require_platform_ref(self.container_binding_ref, prefix="binding:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        return self


class HarvestToCustodyIntent(StrictGameplayModel):
    """Harvest source request; Inventory fixes custody coordinates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    harvest_event_id: str = Field(min_length=1)
    expected_harvest_revision: int = Field(ge=1)
    expected_inventory_stream_revision: int = Field(ge=0)
    command_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class OwnerBoundEnvironmentConsumerContent(ClosedFamilyContent):
    source_event_family_ref: str = Field(min_length=1)
    weather_ref: str | None = None
    target_state_definition_ref: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)
    effect_ref: str = Field(min_length=1)
    state_ref: str = Field(min_length=1)
    magnitude: int = Field(ge=0)
    stack_key: str = Field(min_length=1)
    stack_policy: Literal["add", "replace", "refresh", "reject"]
    stack_limit: int = Field(ge=1)
    expiry_policy: Literal["none", "scheduled"]
    expires_after_ticks: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_slots(self) -> "OwnerBoundEnvironmentConsumerContent":
        _require_platform_ref(self.source_event_family_ref, prefix="event:")
        if self.weather_ref is not None:
            if not self.weather_ref.startswith("weather:") or not self.weather_ref.removeprefix("weather:"):
                raise ValueError("platform_reference_invalid")
        target_ref = self.target_state_definition_ref
        if target_ref.startswith("definition:"):
            _require_platform_ref(target_ref, prefix="definition:")
        elif not target_ref.startswith("state:") or not target_ref.removeprefix("state:"):
            raise ValueError("platform_reference_invalid")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        if not self.effect_ref.startswith("effect:") or not self.effect_ref.removeprefix("effect:"):
            raise ValueError("platform_reference_invalid")
        if not self.state_ref.startswith("state:") or not self.state_ref.removeprefix("state:"):
            raise ValueError("platform_reference_invalid")
        return self


class OwnerBoundEnvironmentConsumerIntent(StrictGameplayModel):
    """Weather/assignment evidence request; Survival derives the target actor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    weather_event_id: str = Field(min_length=1)
    region_assignment_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class DomainAcceptanceMarkerContent(ClosedFamilyContent):
    source_fact_family_ref: str = Field(min_length=1)
    source_item_definition_ref: str = Field(min_length=1)
    marker_definition_ref: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "DomainAcceptanceMarkerContent":
        _require_platform_ref(self.source_fact_family_ref, prefix="fact:")
        _require_platform_ref(self.source_item_definition_ref, prefix="item:")
        _require_platform_ref(self.marker_definition_ref, prefix="definition:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        return self


class DomainAcceptanceMarkerIntent(StrictGameplayModel):
    """Owner-local marker request from one committed source fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_id: str = Field(min_length=1)
    command_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


class PrivateFollowOnContent(ClosedFamilyContent):
    source_fact_family_ref: str = Field(min_length=1)
    marker_definition_ref: str = Field(min_length=1)
    participant_binding_ref: str = Field(min_length=1)
    policy_revision_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_slots(self) -> "PrivateFollowOnContent":
        _require_platform_ref(self.source_fact_family_ref, prefix="fact:")
        _require_platform_ref(self.marker_definition_ref, prefix="definition:")
        _require_platform_ref(self.participant_binding_ref, prefix="binding:")
        _require_platform_ref(self.policy_revision_ref, prefix="policy:")
        return self


class PrivateFollowOnIntent(StrictGameplayModel):
    """Private follow-on request sourced from one committed public notice."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    notice_event_id: str = Field(min_length=1)
    expected_notice_revision: int = Field(ge=1)
    command_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)


@dataclass(frozen=True)
class ClosedGameplayFamily:
    family_ref: str
    contract_ref: str
    contract_kind: str
    descriptor_ref: str
    owner_ref: str
    stream_pattern: str
    event_types: tuple[str, ...]
    privacy_scope: str
    capability_ref: str
    outcome_family_ref: str
    predicate_family_refs: tuple[str, ...]
    effect_types: tuple[str, ...]
    package_slot_refs: tuple[str, ...]
    content_model: Type[ClosedFamilyContent]
    status: Literal["generic_implemented", "bounded_adapter", "design_only", "blocked"] = "design_only"
    adapter_ref: str | None = None
    blocker_ref: str | None = None


class ClosedFamilyBinding(StrictGameplayModel):
    """Activation-derived, immutable family binding pins."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    family_ref: str = Field(min_length=1)
    package_revision: str = Field(min_length=1)
    content_digest: str = Field(min_length=1)
    declaration_ref: str = Field(min_length=1)
    declaration_digest: str = Field(min_length=1)
    descriptor_ref: str = Field(min_length=1)
    descriptor_revision: str = Field(min_length=1)
    active_set_revision: str = Field(min_length=1)


class ClosedFamilyBlocker(StrictGameplayModel):
    """Evidence-backed blocker; it never authorizes a fallback write."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blocker_ref: str = Field(min_length=1)
    family_ref: str = Field(min_length=1)
    status: Literal["blocked"] = "blocked"
    candidate_values: tuple[str, ...]
    source_refs: tuple[str, ...]
    business_impact: str = Field(min_length=1)
    recommended_decision: str = Field(min_length=1)


CLOSED_GAMEPLAY_FAMILIES: tuple[ClosedGameplayFamily, ...] = (
    ClosedGameplayFamily("recipe_production@1", "inf:construction-recipe-production@1", "settlement", "descriptor:construction-recipe-production@1", "actor_gameplay.construction_production_domain", "gameplay:construction_production:{facility_ref}", ("gameplay.construction_production.run_started", "gameplay.construction_production.run_finished"), "project", "capability:recipe-production@1", "outcome:recipe-production@1", ("predicate:construction-facility-committed@1",), ("effect:recipe-production-run@1",), ("slot:duration@1", "slot:facility-definition@1", "slot:input-items@1", "slot:output-items@1", "slot:qualification@1", "slot:recipe-definition@1"), __import__("app.gameplay.recipe_production_family", fromlist=["RecipeProductionContent"]).RecipeProductionContent, status="generic_implemented", adapter_ref="ConstructionProductionAuthority.settle_recipe_production_start"),
    ClosedGameplayFamily("facility_identity_upgrade@1", "inf:construction-facility-identity-upgrade@1", "settlement", "descriptor:construction-facility-identity-upgrade@1", "actor_gameplay.construction_production_domain", "gameplay:construction_production:{facility_ref}", ("gameplay.construction_production.facility_transformed",), "project", "capability:facility-identity-upgrade@1", "outcome:facility-identity-upgrade@1", ("predicate:construction-facility-acquired@1",), ("effect:facility-identity-upgrade@1",), ("slot:source-definition@1", "slot:target-definition@1", "slot:policy@1", "slot:qualification@1"), FacilityIdentityUpgradeContent, status="generic_implemented", adapter_ref="ConstructionProductionAuthority.settle_facility_identity_upgrade"),
    ClosedGameplayFamily("facility_lifecycle_transition@1", "inf:construction-facility-lifecycle-transition@1", "lifecycle", "descriptor:construction-facility-lifecycle-transition@1", "actor_gameplay.construction_production_domain", "gameplay:construction_production:{facility_ref}", ("gameplay.construction_production.facility_decommissioned",), "project", "capability:facility-lifecycle-transition@1", "outcome:facility-lifecycle-transition@1", ("predicate:construction-facility-acquired@1",), ("effect:facility-lifecycle-transition@1",), ("slot:facility-definition@1", "slot:lifecycle@1", "slot:policy@1"), FacilityLifecycleTransitionContent, status="generic_implemented", adapter_ref="ConstructionProductionAuthority.settle_facility_lifecycle_transition"),
    ClosedGameplayFamily("production_output_certification@1", "inf:construction-production-output-certification@1", "lifecycle", "descriptor:construction-production-output-certification@1", "actor_gameplay.construction_production_domain", "gameplay:construction_production:{facility_ref}", ("gameplay.construction_production.production_output_certified@1",), "project", "capability:production-output-certification@1", "outcome:production-output-certification@1", ("predicate:construction-production-run-completed@1",), ("effect:production-output-certification@1",), ("slot:recipe@1", "slot:output-item@1", "slot:quantity@1", "slot:policy@1"), ProductionOutputCertificationContent, status="generic_implemented", adapter_ref="ConstructionProductionAuthority.settle_production_output_certification"),
    ClosedGameplayFamily("production_output_custody@1", "inf:inventory-production-output-custody@1", "contract_admission", "descriptor:inventory-production-output-custody@1", "actor_gameplay.inventory_domain", "gameplay:inventory:{holder_ref}", ("gameplay.inventory.production_output_received@1",), "project", "capability:production-output-custody@1", "outcome:production-output-custody@1", ("predicate:construction-production-output-certified@1",), ("effect:production-output-custody@1",), ("slot:output-item@1", "slot:holder@1", "slot:container@1", "slot:policy@1"), ProductionOutputCustodyContent, status="generic_implemented", adapter_ref="InventoryAuthorityService.settle_production_output_custody"),
    ClosedGameplayFamily("declared_exchange@1", "inf:economy-declared-exchange@1", "settlement", "descriptor:economy-declared-exchange@1", "actor_gameplay.economy_domain", "gameplay:economy", ("gameplay.economy.package_declared_negotiated_exchange_settled",), "authority_only", "capability:declared-exchange@1", "outcome:declared-exchange@1", ("predicate:declared-source-evidence@1",), ("effect:declared-exchange@1",), ("slot:outcome@1", "slot:tradeable-or-service@1", "slot:policy@1", "slot:eligibility@1"), DeclaredExchangeContent, status="generic_implemented", adapter_ref="EconomyAuthorityService.settle_declared_exchange"),
    ClosedGameplayFamily("fixed_service_exchange@1", "inf:economy-fixed-service-exchange@1", "settlement", "descriptor:economy-fixed-service-exchange@1", "actor_gameplay.economy_domain", "gameplay:economy", ("gameplay.economy.package_declared_negotiated_exchange_settled",), "authority_only", "capability:fixed-service-exchange@1", "outcome:fixed-service-exchange@1", ("predicate:completed-service@1",), ("effect:fixed-service-exchange@1",), ("slot:service@1", "slot:provider-rule@1", "slot:receiver-rule@1", "slot:price-policy@1", "slot:policy@1"), FixedServiceExchangeContent, status="generic_implemented", adapter_ref="EconomyAuthorityService.settle_fixed_service_exchange"),
    ClosedGameplayFamily("bounded_project_budget@1", "inf:economy-bounded-project-budget@1", "lifecycle", "descriptor:economy-bounded-project-budget@1", "actor_gameplay.economy_domain", "gameplay:economy", ("gameplay.economy.public_project_budget_commitment_recorded", "gameplay.economy.budget_reserved", "gameplay.economy.public_project_budget_consumed", "gameplay.economy.public_project_budget_closed"), "authority_only", "capability:bounded-project-budget@1", "outcome:bounded-project-budget@1", ("predicate:project-budget-source@1",), ("effect:bounded-project-budget@1",), ("slot:project@1", "slot:currency@1", "slot:amount@1", "slot:policy@1", "slot:source-work-order@1", "slot:source-project-step@1"), BoundedProjectBudgetContent, status="generic_implemented", adapter_ref="EconomyAuthorityService.settle_bounded_project_budget"),
    ClosedGameplayFamily("harvest_to_custody@1", "inf:inventory-harvest-to-custody@1", "contract_admission", "descriptor:inventory-harvest-to-custody@1", "actor_gameplay.inventory_domain", "gameplay:inventory:{holder_ref}", ("gameplay.inventory.harvest_received@1",), "project", "capability:harvest-to-custody@1", "outcome:harvest-to-custody@1", ("predicate:ecology-grain-harvested@1",), ("effect:harvest-to-custody@1",), ("slot:crop@1", "slot:item@1", "slot:holder@1", "slot:container@1", "slot:policy@1"), HarvestToCustodyContent, status="generic_implemented", adapter_ref="InventoryAuthorityService.settle_harvest_to_custody"),
    ClosedGameplayFamily("owner_bound_environment_consumer@1", "inf:owner-bound-environment-consumer@1", "ecology_consumer", "descriptor:owner-bound-environment-consumer@1", "actor_gameplay.survival_domain", "gameplay:survival:{profile_ref}", ("gameplay.survival.state_applied",), "project", "capability:owner-bound-environment-consumer@1", "outcome:owner-bound-environment-consumer@1", ("predicate:environment-source@1",), ("effect:owner-bound-environment-consumer@1",), ("slot:source-event-family@1", "slot:target-state@1", "slot:policy@1", "slot:effect@1", "slot:lifecycle@1"), OwnerBoundEnvironmentConsumerContent, status="generic_implemented", adapter_ref="SurvivalAuthority.settle_owner_bound_environment_consumer"),
    ClosedGameplayFamily("domain_acceptance_marker@1", "inf:domain-acceptance-marker@1", "contract_admission", "descriptor:domain-acceptance-marker@1", "actor_gameplay.organization_domain", "gameplay:organization:{organization_ref}", ("gameplay.organization.grain_intake_recorded@1",), "project", "capability:domain-acceptance-marker@1", "outcome:domain-acceptance-marker@1", ("predicate:domain-source-fact@1",), ("effect:domain-acceptance-marker@1",), ("slot:source-fact@1", "slot:marker@1", "slot:policy@1"), DomainAcceptanceMarkerContent, status="generic_implemented", adapter_ref="OrganizationAuthority.settle_domain_acceptance_marker"),
    ClosedGameplayFamily("private_follow_on@1", "inf:private-follow-on@1", "contract_admission", "descriptor:private-follow-on@1", "authority:p5:social", "gameplay:social:public-milling-notice-acknowledgment:{participant_ref}", ("gameplay.social.public_milling_notice_acknowledged",), "actor_private", "capability:private-follow-on@1", "outcome:private-follow-on@1", ("predicate:private-source-fact@1",), ("effect:private-follow-on@1",), ("slot:source-fact@1", "slot:marker@1", "slot:participant@1", "slot:policy@1"), PrivateFollowOnContent, status="generic_implemented", adapter_ref="SocialFactAuthority.settle_private_follow_on"),
)


def content_model_for_family(family_ref: str) -> Type[ClosedFamilyContent]:
    for family in CLOSED_GAMEPLAY_FAMILIES:
        if family.family_ref == family_ref:
            return family.content_model
    raise KeyError(family_ref)


def admit_family_binding(
    *,
    family_ref: str,
    package_revision: str,
    content_digest: str,
    declaration_ref: str,
    declaration_digest: str,
    declaration_payload: Mapping[str, object] | None = None,
    descriptor_ref: str,
    descriptor_revision: str,
    active_set_revision: str,
    typed_content: Mapping[str, object],
) -> ClosedFamilyBinding:
    """Validate one exact family binding without selecting authority coordinates."""
    family = next((item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == family_ref), None)
    if family is None:
        raise ValueError("closed_family_unknown")
    if family.status == "blocked":
        raise ValueError(family.blocker_ref or "closed_family_blocked")
    if descriptor_ref != family.descriptor_ref or descriptor_revision != family.descriptor_ref:
        raise ValueError("closed_family_descriptor_mismatch")
    if not declaration_ref.startswith("declaration:") or "@" not in declaration_ref:
        raise ValueError("closed_family_declaration_invalid")
    if not declaration_digest.startswith("sha256:") or not content_digest.startswith("sha256:"):
        raise ValueError("closed_family_digest_invalid")
    if declaration_payload is not None:
        payload = dict(declaration_payload)
        if payload.get("declaration_ref") != declaration_ref:
            raise ValueError("closed_family_declaration_mismatch")
        if declaration_digest != _canonical_digest(payload):
            raise ValueError("closed_family_declaration_digest_mismatch")
    validated_content = family.content_model.model_validate(dict(typed_content))
    if content_digest != _canonical_digest(validated_content.model_dump(mode="json", exclude_none=True)):
        raise ValueError("closed_family_content_digest_mismatch")
    return ClosedFamilyBinding(
        family_ref=family_ref,
        package_revision=package_revision,
        content_digest=content_digest,
        declaration_ref=declaration_ref,
        declaration_digest=declaration_digest,
        descriptor_ref=descriptor_ref,
        descriptor_revision=descriptor_revision,
        active_set_revision=active_set_revision,
    )


def select_family_binding(bindings: tuple[ClosedFamilyBinding, ...]) -> ClosedFamilyBinding:
    """Select one exact binding; ordering never resolves ambiguity."""
    if not bindings:
        raise ValueError("closed_family_binding_zero")
    if len(bindings) != 1:
        raise ValueError("closed_family_binding_ambiguous")
    return bindings[0]


def family_binding_is_valid(
    *,
    family_ref: str,
    manifest: object,
    declaration: object,
    declaration_payload: Mapping[str, object],
    request: object,
    definition: object,
    binding: object,
    active_set_revision: str,
    typed_content: ClosedFamilyContent,
) -> bool:
    """Validate an activation-derived family binding before owner execution."""
    family = next((item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == family_ref), None)
    if family is None or family.status == "blocked":
        return False
    try:
        content_payload = typed_content.model_dump(mode="json", exclude_none=True)
        definition_payload = dict(definition.typed_content)
        return bool(
            request.capability_ref == family.capability_ref
            and request.declaration_ref == declaration.declaration_ref
            and request.source_package_revision == manifest.patch_revision_id
            and declaration.outcome_family_ref == family.outcome_family_ref
            and declaration.source_package_revision == manifest.patch_revision_id
            and tuple(item.predicate_family_ref for item in request.typed_read_requirements) == family.predicate_family_refs
            and tuple(request.proposal_effect_types) == family.effect_types
            and definition.source_package_revision == manifest.patch_revision_id
            and binding.family_ref == family_ref
            and binding.package_revision == manifest.patch_revision_id
            and binding.content_digest == manifest.content_digest
            and binding.family_content_digest == _canonical_digest(content_payload)
            and _canonical_digest(definition_payload) == binding.family_content_digest
            and binding.definition_ref == definition.definition_ref
            and binding.declaration_ref == declaration.declaration_ref
            and binding.declaration_digest == declaration.declaration_digest
            and declaration.declaration_digest == _canonical_digest(dict(declaration_payload))
            and binding.descriptor_ref == family.descriptor_ref
            and binding.descriptor_revision == family.descriptor_ref
            and binding.active_patch_set_revision == active_set_revision
        )
    except (AttributeError, TypeError, ValueError):
        return False


PRODUCTION_OUTPUT_CUSTODY_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:production-output-custody-committed-facts@1",
    family_ref="production_output_custody@1",
    candidate_values=(
        "output quantity: absent from committed Construction run_finished",
        "holder mapping: facility_acquired.owner_ref is not an admitted Inventory holder",
        "destination container: no unique open Inventory container is committed",
    ),
    source_refs=(
        "backend/app/gameplay/construction_production_runtime.py:run_finished",
        "backend/app/gameplay/inventory_runtime.py:record_output_receipt",
        "docs/superpowers/plans/world-character-siming-authority-mainline/2026-08-29-closed-generic-gameplay-families-implementation-plan.md:105",
    ),
    business_impact="A custody append would require caller/default inference for quantity, holder, or container and would violate owner-bound provenance.",
    recommended_decision="Commit a quantity-bearing production provenance pin, an explicit source-to-holder mapping, and a deterministic unique-container rule, each with revision/privacy contracts.",
)

HARVEST_TO_CUSTODY_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:harvest-to-custody-genericity@1",
    family_ref="harvest_to_custody@1",
    candidate_values=(
        "source harvest: fixed to gameplay.ecology.grain_harvested with grain:wheat yield 10",
        "holder/container: fixed to organization:district-milling-cooperative and container:district-milling-cooperative:grain-intake",
        "item: fixed to grain:wheat@1; no second admitted harvest item family is committed",
    ),
    source_refs=(
        "backend/app/gameplay/inventory_runtime.py:settle_harvest_to_custody",
        "backend/tests/test_harvest_to_custody_family.py:test_harvest_to_custody_consumes_the_one_admitted_wheat_content",
        "backend/tests/test_inf3ab_grain_harvest_inventory_custody.py:test_inf3ab_commits_owner_bound_grain_custody_receipt",
    ),
    business_impact="The family still hard-codes the district-milling wheat harvest intake row and cannot admit a second harvest content instance without a new committed crop/source fact or a new generic custody selector.",
    recommended_decision="Retain the existing zero-write narrow row until a separately admitted harvest species/source contract is added, then bind the family to that explicit contract.",
)

DOMAIN_ACCEPTANCE_GENERICITY_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:domain-acceptance-marker-genericity@1",
    family_ref="domain_acceptance_marker@1",
    candidate_values=(
        "source fact: fixed to gameplay.inventory.grain_harvest_received@1 from the district milling cooperative; marker is grain_intake",
        "sibling acceptance: production_work_contribution_accepted@1 exists, but it is a distinct event family with organization:summary privacy rather than the fixed project-scoped marker",
        "immutable family content: no committed domain-acceptance-marker manifest pair exists under closed-generic/domain-acceptance-marker",
        "organization scope: fixed to organization:district-milling-cooperative with no second admitted domain-acceptance source-to-marker contract",
    ),
    source_refs=(
        "backend/app/gameplay/organization_government_runtime.py:settle_domain_acceptance_marker",
        "backend/app/gameplay/organization_government_runtime.py:accept_production_work_contribution",
        "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_stays_bounded_to_the_exact_inventory_source_chain",
        "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_blocker_matches_committed_manifest_and_sibling_acceptance_evidence",
        "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_blocker_records_missing_family_manifests_and_real_privacy_mismatch",
        "backend/app/gameplay/organization_government_runtime.py:work_contribution_acceptance_view_for",
        "backend/app/gameplay/governed_contract_catalog.py:1309",
        "backend/app/gameplay/event_schema_registry.py:CLOSED_GENERIC_DOMAIN_ACCEPTANCE_EVENT_SCHEMAS",
        "backend/tests/test_inf4v_production_work_contribution_acceptance.py:test_inf4v_accepts_only_production_evidence_with_committed_organization_schedule",
        "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/domain-acceptance-marker/",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-4/2026-08-27-inf-4v-production-work-contribution-acceptance-owner-admission-design.md",
    ),
    business_impact="The family only reifies the district-milling grain-intake marker. The only other real Organization acceptance source has a different event/privacy contract, and no immutable family content pair binds either source to this marker.",
    recommended_decision="Keep the exact district-milling marker as a bounded zero-write adapter until a separately admitted source-to-marker contract and two immutable family manifests are committed.",
)

PRIVATE_FOLLOW_ON_GENERICITY_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:private-follow-on-genericity@1",
    family_ref="private_follow_on@1",
    candidate_values=(
        "source fact: fixed to gameplay.social.public_milling_notice_recorded@1/public-milling notice acknowledgment lineage",
        "participants: fixed to the public milling provider plus one committed receiver",
        "privacy: fixed actor-private acknowledgment pair; no second admitted public notice source row is committed",
    ),
    source_refs=(
        "backend/app/gameplay/organization_government_runtime.py:record_public_milling_notice",
        "backend/app/gameplay/p5/social_knowledge.py:record_public_milling_notice_social_acknowledgment",
        "backend/app/gameplay/p5/social_knowledge.py:settle_private_follow_on",
        "backend/tests/test_inf4am_public_milling_notice.py:test_inf4am_records_exact_milling_notice_and_replays",
        "backend/tests/test_inf4ao_public_milling_social_ack.py:test_inf4ao_records_exactly_two_actor_private_acknowledgments",
        "backend/tests/test_private_follow_on_family.py:test_private_follow_on_derives_two_actor_private_targets_from_notice",
        "backend/tests/test_private_follow_on_family.py:test_private_follow_on_stays_bounded_to_the_exact_notice_chain",
    ),
    business_impact="A second public notice source fact and participant/privacy contract are not committed; generic fanout would violate the closed social boundary.",
    recommended_decision="The second source is now admitted through the closed generic public-workshop notice binding; retain this historical blocker text only for compatibility.",
)

BOUNDED_PROJECT_BUDGET_GENERICITY_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:bounded-project-budget-genericity@1",
    family_ref="bounded_project_budget@1",
    candidate_values=(
        "commitment: fixed one municipal public-project step commitment on project-step:public-project:workshop-bench@1",
        "reservation: fixed one owner-derived currency:local account reservation on the same municipal chain",
        "consumption: fixed one authority-only consumed marker from INF-4AG plus INF-2AH",
        "close: fixed one authority-only terminal close marker from INF-2AI plus INF-4AJ",
        "amount/currency: hard-coded at 12 currency:local with no second admitted budget content instance",
    ),
    source_refs=(
        "backend/app/gameplay/economy_runtime.py:settle_bounded_project_budget",
        "backend/tests/test_inf2af_public_project_budget_commitment.py:test_inf2af_records_one_fixed_budget_commitment_from_public_project_step",
        "backend/tests/test_inf2ah_public_project_budget_reservation.py:test_inf2ah_reserves_exact_public_project_commitment_from_unique_owner_account",
        "backend/tests/test_inf2ai_public_project_budget_consumption.py:test_inf2ai_consumes_one_reserved_public_project_budget_from_completed_activity",
        "backend/tests/test_inf2ak_public_project_budget_close.py:test_inf2ak_closes_consumed_budget_after_matching_project_execution",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-27-inf-2af-public-project-budget-commitment-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-27-inf-2ah-public-project-budget-reservation-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2ai-public-project-budget-consumption-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2ak-public-project-budget-close-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v5-public-workshop-session.manifest.json",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v6-public-milling-session.manifest.json",
    ),
    business_impact="No second committed project budget definition is available to prove content-generic lifecycle semantics without choosing caller-supplied terms.",
    recommended_decision="Admit a second project budget source and immutable amount/currency policy before generic promotion.",
)

CLOSED_FAMILY_GENERICITY_BLOCKERS = ()

BOUNDED_PROJECT_BUDGET_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:bounded-project-budget-genericity@1",
    family_ref="bounded_project_budget@1",
    candidate_values=(
        "commitment: fixed one municipal public-project step commitment on project-step:public-project:workshop-bench@1",
        "reservation: fixed one owner-derived currency:local account reservation on the same municipal chain",
        "consumption: fixed one authority-only consumed marker from INF-4AG plus INF-2AH",
        "close: fixed one authority-only terminal close marker from INF-2AI plus INF-4AJ",
        "amount/currency: hard-coded at 12 currency:local with no second admitted budget content instance",
    ),
    source_refs=(
        "backend/app/gameplay/economy_runtime.py:settle_bounded_project_budget",
        "backend/tests/test_inf2af_public_project_budget_commitment.py:test_inf2af_records_one_fixed_budget_commitment_from_public_project_step",
        "backend/tests/test_inf2ah_public_project_budget_reservation.py:test_inf2ah_reserves_exact_public_project_commitment_from_unique_owner_account",
        "backend/tests/test_inf2ai_public_project_budget_consumption.py:test_inf2ai_consumes_one_reserved_public_project_budget_from_completed_activity",
        "backend/tests/test_inf2ak_public_project_budget_close.py:test_inf2ak_closes_consumed_budget_after_matching_project_execution",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-27-inf-2af-public-project-budget-commitment-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-27-inf-2ah-public-project-budget-reservation-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2ai-public-project-budget-consumption-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2ak-public-project-budget-close-owner-admission-design.md",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v5-public-workshop-session.manifest.json",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v6-public-milling-session.manifest.json",
    ),
    business_impact="The family is closed over one municipal public-project budget lifecycle and does not yet prove a second admitted project budget content instance or a reusable budget selector.",
    recommended_decision="Keep the current bounded vertical as the accepted municipal budget path until a second project budget source/content row is separately admitted.",
)

DOMAIN_ACCEPTANCE_MARKER_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:domain-acceptance-marker-genericity@1",
    family_ref="domain_acceptance_marker@1",
    candidate_values=(
        "source fact: fixed to gameplay.inventory.grain_harvest_received@1 from the district milling cooperative",
        "sibling acceptance: production_work_contribution_accepted@1 exists, but it is a distinct event family with organization:summary privacy rather than the fixed project-scoped marker",
        "immutable family content: no committed domain-acceptance-marker manifest pair exists under closed-generic/domain-acceptance-marker",
        "organization scope: fixed to organization:district-milling-cooperative with no second admitted domain-acceptance source-to-marker contract",
    ),
    source_refs=(
        "backend/app/gameplay/organization_government_runtime.py:settle_domain_acceptance_marker",
        "backend/app/gameplay/organization_government_runtime.py:accept_production_work_contribution",
        "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_derives_organization_from_committed_inventory_source",
        "backend/tests/test_inf4ap_grain_intake_activity.py:test_inf4ap_records_exact_project_grain_intake",
        "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_blocker_matches_committed_manifest_and_sibling_acceptance_evidence",
        "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_blocker_records_missing_family_manifests_and_real_privacy_mismatch",
        "backend/app/gameplay/organization_government_runtime.py:work_contribution_acceptance_view_for",
        "backend/app/gameplay/governed_contract_catalog.py:1309",
        "backend/app/gameplay/event_schema_registry.py:CLOSED_GENERIC_DOMAIN_ACCEPTANCE_EVENT_SCHEMAS",
        "backend/tests/test_inf4v_production_work_contribution_acceptance.py:test_inf4v_accepts_only_production_evidence_with_committed_organization_schedule",
        "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/domain-acceptance-marker/",
        "docs/superpowers/specs/world-character-siming-authority-mainline/inf-4/2026-08-27-inf-4v-production-work-contribution-acceptance-owner-admission-design.md",
    ),
    business_impact="The family only reifies the district-milling grain-intake marker. The only other real Organization acceptance source has a different event/privacy contract, and no immutable family content pair binds either source to this marker.",
    recommended_decision="Keep the exact district-milling marker as a bounded zero-write adapter until a separately admitted source-to-marker contract and two immutable family manifests are committed.",
)

PRIVATE_FOLLOW_ON_BLOCKER = ClosedFamilyBlocker(
    blocker_ref="blocker:private-follow-on-genericity@1",
    family_ref="private_follow_on@1",
    candidate_values=(
        "source fact: fixed to gameplay.social.public_milling_notice_recorded@1/public-milling notice acknowledgment lineage",
        "participants: fixed to the public milling provider plus one committed receiver",
        "privacy: fixed actor-private acknowledgment pair; no second admitted public notice source row is committed",
    ),
    source_refs=(
        "backend/app/gameplay/organization_government_runtime.py:record_public_milling_notice",
        "backend/app/gameplay/p5/social_knowledge.py:record_public_milling_notice_social_acknowledgment",
        "backend/app/gameplay/p5/social_knowledge.py:settle_private_follow_on",
        "backend/tests/test_inf4am_public_milling_notice.py:test_inf4am_records_exact_milling_notice_and_replays",
        "backend/tests/test_inf4ao_public_milling_social_ack.py:test_inf4ao_records_exactly_two_actor_private_acknowledgments",
        "backend/tests/test_private_follow_on_family.py:test_private_follow_on_derives_two_actor_private_targets_from_notice",
        "backend/tests/test_private_follow_on_family.py:test_private_follow_on_stays_bounded_to_the_exact_notice_chain",
    ),
    business_impact="A second public notice source fact and participant/privacy contract are not committed; generic fanout would violate the closed social boundary.",
    recommended_decision="Retain the current narrow private follow-on row until a second separately admitted source fact and participant binding policy are available.",
)


__all__ = [
    "CLOSED_GAMEPLAY_FAMILIES",
    "ClosedGameplayFamily",
    "ClosedFamilyContent",
    "ClosedFamilyBinding",
    "ClosedFamilyBlocker",
    "FacilityIdentityUpgradeIntent",
    "FacilityLifecycleTransitionIntent",
    "ProductionOutputCertificationIntent",
    "ProductionOutputCustodyIntent",
    "DeclaredExchangeIntent",
    "FixedServiceExchangeIntent",
    "HarvestToCustodyIntent",
    "OwnerBoundEnvironmentConsumerIntent",
    "DomainAcceptanceMarkerIntent",
    "PrivateFollowOnIntent",
    "BoundedProjectBudgetIntent",
    "BoundedProjectBudgetProjectStepIntent",
    "BoundedProjectBudgetConstructionIntent",
    "BoundedProjectBudgetReservationIntent",
    "BoundedProjectBudgetConsumptionIntent",
    "BoundedProjectBudgetCloseIntent",
    "PRODUCTION_OUTPUT_CUSTODY_BLOCKER",
    "HARVEST_TO_CUSTODY_BLOCKER",
    "ENVIRONMENT_CONSUMER_GENERICITY_BLOCKER",
    "DOMAIN_ACCEPTANCE_GENERICITY_BLOCKER",
    "PRIVATE_FOLLOW_ON_GENERICITY_BLOCKER",
    "BOUNDED_PROJECT_BUDGET_GENERICITY_BLOCKER",
    "CLOSED_FAMILY_GENERICITY_BLOCKERS",
    "BOUNDED_PROJECT_BUDGET_BLOCKER",
    "DOMAIN_ACCEPTANCE_MARKER_BLOCKER",
    "PRIVATE_FOLLOW_ON_BLOCKER",
    "admit_family_binding",
    "select_family_binding",
    "family_binding_is_valid",
    "content_model_for_family",
]
