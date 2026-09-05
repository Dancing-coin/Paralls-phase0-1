"""Explicit event-type/version allowlist for opt-in Gameplay store writes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class EventSchemaRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class EventSchemaRegistration:
    event_type: str
    schema_version: int
    schema_digest: str


PHASE2A_WORK_INTENT_EVENT_SCHEMAS = (
    EventSchemaRegistration("gameplay.work.respond_shift", 1, "sha256:phase2a:respond_shift:v1"),
    EventSchemaRegistration("gameplay.work.start_work", 1, "sha256:phase2a:start_work:v1"),
    EventSchemaRegistration("gameplay.work.finish_work", 1, "sha256:phase2a:finish_work:v1"),
    EventSchemaRegistration("gameplay.work.report_absence", 1, "sha256:phase2a:report_absence:v1"),
    EventSchemaRegistration("gameplay.work.request_break", 1, "sha256:phase2a:request_break:v1"),
)


INF4AI_P5_ACTOR_PRIVATE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.social.handshake_shared_experience_recorded",
        1,
        "sha256:963801afdb239c431578691d933c51e120dd02dd36f0c2c460f894ecec5b1810",
    ),
)

INF4AO_P5_ACTOR_PRIVATE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.social.public_milling_notice_acknowledged",
        1,
        "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ),
)


INF3_GRAIN_HARVEST_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.ecology.grain_crop.admitted",
        1,
        "sha256:inf3:ecology:grain-crop-admitted:v1",
    ),
    EventSchemaRegistration(
        "gameplay.ecology.grain_harvested",
        1,
        "sha256:inf3:ecology:grain-harvested:v1",
    ),
)

INF3AB_GRAIN_CUSTODY_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.inventory.grain_harvest_received@1",
        1,
        "sha256:inf3ab:inventory:grain-harvest-received:v1",
    ),
)

INF4AP_GRAIN_INTAKE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.organization.grain_intake_recorded@1",
        1,
        "sha256:inf4ap:organization:grain-intake-recorded:v1",
    ),
)

CLOSED_GENERIC_DOMAIN_ACCEPTANCE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.organization.domain_acceptance_marked@1",
        1,
        "sha256:closed-generic:organization:domain-acceptance-marked:v1",
    ),
)

INF2AN_GRAIN_INTAKE_ACCEPTANCE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.economy.grain_intake_accepted@1",
        1,
        "sha256:inf2an:economy:grain-intake-accepted:v1",
    ),
)

INF2AO_PRODUCTION_OUTPUT_MARKET_ELIGIBILITY_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.economy.production_output_market_eligible@1",
        1,
        "sha256:inf2ao:economy:production-output-market-eligible:v1",
    ),
)

CONSTRUCTION_JOB_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.construction_production.construction_job_started@1",
        1,
        "sha256:construction:job-started:v1",
    ),
    EventSchemaRegistration(
        "gameplay.construction_production.construction_job_completed@1",
        1,
        "sha256:construction:job-completed:v1",
    ),
    EventSchemaRegistration(
        "gameplay.construction_production.construction_job_failed@1",
        1,
        "sha256:construction:job-failed:v1",
    ),
)

CONSTRUCTION_PRODUCTION_FAILURE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.construction_production.run_failed@1",
        1,
        "sha256:construction:run-failed:v1",
    ),
)

CONSTRUCTION_MAINTENANCE_OBLIGATION_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.construction_production.maintenance_obligation_created",
        1,
        "sha256:construction:maintenance-obligation-created:v1",
    ),
)

CONSTRUCTION_OUTPUT_CERTIFICATION_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.construction_production.production_output_certified@1",
        1,
        "sha256:construction:production-output-certified:v1",
    ),
)

INVENTORY_OUTPUT_CUSTODY_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.inventory.production_output_received@1",
        1,
        "sha256:inventory:production-output-received:v1",
    ),
)

CONSTRUCTION_LIFECYCLE_EVENT_SCHEMAS = (
    EventSchemaRegistration("gameplay.construction_production.facility_acquired", 1, "sha256:construction:facility-acquired:v1"),
    EventSchemaRegistration("gameplay.construction_production.facility_transformed", 1, "sha256:construction:facility-transformed:v1"),
    EventSchemaRegistration("gameplay.construction_production.facility_decommissioned", 1, "sha256:construction:facility-decommissioned:v1"),
    EventSchemaRegistration("gameplay.construction_production.run_started", 1, "sha256:construction:run-started:v1"),
    EventSchemaRegistration("gameplay.construction_production.run_finished", 1, "sha256:construction:run-finished:v1"),
)

CONSTRUCTION_MAINTENANCE_EVENT_SCHEMAS = (
    EventSchemaRegistration("gameplay.construction_production.facility_repaired", 1, "sha256:construction:facility-repaired:v1"),
    EventSchemaRegistration("gameplay.construction_production.facility_repair_compensated", 1, "sha256:construction:facility-repair-compensated:v1"),
    EventSchemaRegistration("gameplay.construction_production.maintenance_state_applied", 1, "sha256:construction:maintenance-state-applied:v1"),
    EventSchemaRegistration("gameplay.construction_production.maintenance_state_obligation_opened", 1, "sha256:construction:maintenance-state-obligation-opened:v1"),
    EventSchemaRegistration("gameplay.construction_production.maintenance_state_obligation_settled", 1, "sha256:construction:maintenance-state-obligation-settled:v1"),
    EventSchemaRegistration("gameplay.construction_production.maintenance_state_expired", 1, "sha256:construction:maintenance-state-expired:v1"),
    EventSchemaRegistration("gameplay.construction_production.maintenance_state_dispelled", 1, "sha256:construction:maintenance-state-dispelled:v1"),
    EventSchemaRegistration("gameplay.construction_production.maintenance_state_obligation_cancelled", 1, "sha256:construction:maintenance-state-obligation-cancelled:v1"),
)


class EventSchemaRegistry:
    def __init__(self) -> None:
        self._registrations: dict[tuple[str, int], EventSchemaRegistration] = {}

    def register(self, registration: EventSchemaRegistration) -> None:
        key = (registration.event_type, registration.schema_version)
        if not registration.event_type or registration.schema_version < 1 or not registration.schema_digest:
            raise EventSchemaRegistryError("event_schema_registration_invalid")
        existing = self._registrations.get(key)
        if existing is not None:
            if existing.schema_digest != registration.schema_digest:
                raise EventSchemaRegistryError("event_schema_digest_conflict")
            raise EventSchemaRegistryError("event_schema_registration_duplicate")
        self._registrations[key] = registration

    def require(self, event_type: str, schema_version: int) -> None:
        if (event_type, schema_version) not in self._registrations:
            raise EventSchemaRegistryError("event_schema_unregistered")

    def get(self, event_type: str, schema_version: int) -> EventSchemaRegistration:
        try:
            return self._registrations[(event_type, schema_version)]
        except KeyError as exc:
            raise EventSchemaRegistryError("event_schema_unregistered") from exc

    def export_snapshot(self) -> dict[str, Any]:
        """Return the immutable schema identities required to reopen a store."""
        return {
            "registry_schema_version": 1,
            "registrations": [
                {
                    "event_type": registration.event_type,
                    "schema_version": registration.schema_version,
                    "schema_digest": registration.schema_digest,
                }
                for _, registration in sorted(self._registrations.items())
            ],
        }

    @classmethod
    def from_snapshot(cls, snapshot: object) -> "EventSchemaRegistry":
        if not isinstance(snapshot, dict) or snapshot.get("registry_schema_version") != 1:
            raise EventSchemaRegistryError("event_schema_registry_snapshot_unsupported")
        values = snapshot.get("registrations")
        if not isinstance(values, list):
            raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid")
        registry = cls()
        try:
            for value in values:
                if not isinstance(value, dict):
                    raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid")
                registry.register(
                    EventSchemaRegistration(
                        event_type=str(value["event_type"]),
                        schema_version=int(value["schema_version"]),
                        schema_digest=str(value["schema_digest"]),
                    )
                )
        except (KeyError, TypeError, ValueError, EventSchemaRegistryError) as exc:
            if isinstance(exc, EventSchemaRegistryError) and exc.args and exc.args[0] in {
                "event_schema_registration_duplicate",
                "event_schema_digest_conflict",
            }:
                raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid") from exc
            if isinstance(exc, EventSchemaRegistryError):
                raise
            raise EventSchemaRegistryError("event_schema_registry_snapshot_invalid") from exc
        return registry


_GENERAL_ECONOMY_PLATFORM_EVENTS = (
    "gameplay.economy.currency_issuance_recorded@1", "gameplay.economy.fx_fixing_recorded@1",
    "gameplay.economy.ledger_posted@1", "gameplay.economy.hold_recorded@1",
    "gameplay.economy.obligation_recorded@1", "gameplay.economy.population_market_signal_recorded@1",
    "gameplay.economy.delivery_settlement_recorded@1", "gameplay.economy.organization_period_recorded@1",
    "gameplay.economy.tax_obligation_recorded@1", "gameplay.economy.market_quote_recorded@1",
    "gameplay.economy.market_order_recorded@1", "gameplay.economy.market_clearing_recorded@1",
    "gameplay.economy.credit_facility_recorded@1", "gameplay.economy.insurance_policy_recorded@1",
    "gameplay.economy.security_holding_recorded@1", "gameplay.economy.insolvency_resolution_recorded@1",
    "gameplay.economy.regional_macro_period_closed@1",
    "gameplay.economy.organization_recipe_accepted@1",
    "gameplay.economy.government_recipe_accepted@1",
    "gameplay.contract.ogs_social_conflict_eligibility_accepted@1",
)


def register_general_economy_platform_event_schemas(registry: EventSchemaRegistry) -> None:
    for event_type in _GENERAL_ECONOMY_PLATFORM_EVENTS:
        registration = EventSchemaRegistration(event_type, 1, f"sha256:general-economy-platform:{event_type}:v1")
        try:
            registry.register(registration)
        except EventSchemaRegistryError:
            if registry.get(event_type, 1) != registration:
                raise


_GENERAL_ECOLOGY_PLATFORM_EVENTS = (
    "gameplay.ecology.region.recorded@1",
    "gameplay.ecology.cell.recorded@1",
    "gameplay.ecology.environment.recorded@1",
    "gameplay.ecology.resource.recorded@1",
    "gameplay.ecology.crop.recorded@1",
    "gameplay.ecology.species.recorded@1",
    "gameplay.ecology.region_period_closed@1",
    "gameplay.ecology_hazard.hazard_admitted@1",
    "gameplay.ecology_hazard.hazard_activated@1",
    "gameplay.ecology_hazard.hazard_decayed@1",
    "gameplay.ecology_hazard.hazard_recovered@1",
    "gameplay.ecology_hazard.hazard_terminal@1",
    "gameplay.ecology_hazard.hazard_propagated@1",
    "gameplay.ecology.population_signal_recorded@1",
)


def register_general_ecology_platform_event_schemas(registry: EventSchemaRegistry) -> None:
    for event_type in _GENERAL_ECOLOGY_PLATFORM_EVENTS:
        registration = EventSchemaRegistration(event_type, 1, f"sha256:general-ecology-platform:{event_type}:v1")
        try:
            registry.register(registration)
        except EventSchemaRegistryError:
            if registry.get(event_type, 1) != registration:
                raise


_GENERAL_INVENTORY_PLATFORM_EVENTS = (
    "gameplay.inventory.item_instantiated@1", "gameplay.inventory.lot_created@1",
    "gameplay.inventory.container_recorded@1", "gameplay.inventory.custody_recorded@1",
    "gameplay.inventory.custody_transferred@1", "gameplay.inventory.custody_consumed@1",
    "gameplay.inventory.custody_lost@1", "gameplay.inventory.custody_rejected@1",
    "gameplay.inventory.reservation_opened@1", "gameplay.inventory.reservation_consumed@1",
    "gameplay.inventory.reservation_released@1", "gameplay.inventory.reservation_expired@1",
    "gameplay.inventory.lot_split@1", "gameplay.inventory.lot_merged@1",
    "gameplay.inventory.condition_recorded@1", "gameplay.inventory.transport_in_transit@1",
    "gameplay.inventory.transport_delivered@1", "gameplay.inventory.transport_lost@1",
    "gameplay.inventory.transport_rejected@1",
)


_ORGANIZATION_GOVERNMENT_SOCIAL_PLATFORM_EVENTS = (
    "gameplay.organization.lifecycle_transitioned@1",
    "gameplay.organization.membership_delegation_recorded@1",
    "gameplay.organization.operating_period_recorded@1",
    "gameplay.organization.commitment_budget_proposed@1",
    "gameplay.government.policy_lifecycle_recorded@1",
    "gameplay.government.permit_inspection_case_recorded@1",
    "gameplay.government.tax_treasury_project_proposed@1",
    "gameplay.government.notice_audit_recorded@1",
    "gameplay.social.identity_relationship_recorded@1",
    "gameplay.social.household_group_recorded@1",
    "gameplay.social.norm_conflict_recorded@1",
    "gameplay.social.private_projection_recorded@1",
    "gameplay.social.population_signal_recorded@1",
)

_STORMNIGHT_SCRIPTED_MYSTERY_EVENTS = (
    "gameplay.p5.mystery.case_opened@1",
    "gameplay.p5.mystery.statement_recorded@1",
    "gameplay.p5.mystery.accusation_submitted@1",
    "gameplay.p5.mystery.case_outcome_resolved@1",
)


def register_general_inventory_platform_event_schemas(registry: EventSchemaRegistry) -> None:
    for event_type in _GENERAL_INVENTORY_PLATFORM_EVENTS:
        registration = EventSchemaRegistration(event_type, 1, f"sha256:general-inventory-platform:{event_type}:v1")
        try:
            registry.register(registration)
        except EventSchemaRegistryError:
            if registry.get(event_type, 1) != registration:
                raise


def register_organization_government_social_platform_event_schemas(
    registry: EventSchemaRegistry,
) -> None:
    """Register the source-controlled schema bundle for the federated OGS portfolio."""
    for event_type in _ORGANIZATION_GOVERNMENT_SOCIAL_PLATFORM_EVENTS:
        registration = EventSchemaRegistration(
            event_type,
            1,
            f"sha256:organization-government-social-platform:{event_type}:v1",
        )
        try:
            registry.register(registration)
        except EventSchemaRegistryError:
            if registry.get(event_type, 1) != registration:
                raise


def register_stormnight_scripted_mystery_event_schemas(registry: EventSchemaRegistry) -> None:
    """Register the additive case event bundle for the Stormnight package."""
    for event_type in _STORMNIGHT_SCRIPTED_MYSTERY_EVENTS:
        registration = EventSchemaRegistration(
            event_type,
            1,
            f"sha256:stormnight-copper-sanatorium:{event_type}:v1",
        )
        try:
            registry.register(registration)
        except EventSchemaRegistryError:
            if registry.get(event_type, 1) != registration:
                raise


def create_stormnight_event_schema_registry() -> EventSchemaRegistry:
    registry = EventSchemaRegistry()
    register_stormnight_scripted_mystery_event_schemas(registry)
    return registry


def register_phase2a_work_intent_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in PHASE2A_WORK_INTENT_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf4ai_p5_actor_private_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the one source-controlled INF-4AI schema into an existing registry."""

    for registration in INF4AI_P5_ACTOR_PRIVATE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf4ao_p5_actor_private_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the exact INF-4AO social acknowledgment schema."""

    for registration in INF4AO_P5_ACTOR_PRIVATE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf3_grain_harvest_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the fixed INF-3 Ecology grain row schemas."""

    for registration in INF3_GRAIN_HARVEST_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf3ab_grain_custody_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the fixed Ecology-to-Inventory grain custody schema."""

    for registration in INF3AB_GRAIN_CUSTODY_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf4ap_grain_intake_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the fixed Inventory-to-Organization grain intake schema."""

    for registration in INF4AP_GRAIN_INTAKE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_closed_generic_domain_acceptance_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in CLOSED_GENERIC_DOMAIN_ACCEPTANCE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf2an_grain_intake_acceptance_event_schemas(
    registry: EventSchemaRegistry,
) -> None:
    """Install the fixed Organization-to-Economy grain acceptance schema."""

    for registration in INF2AN_GRAIN_INTAKE_ACCEPTANCE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inf2ao_production_output_market_eligibility_event_schemas(
    registry: EventSchemaRegistry,
) -> None:
    """Install the exact INF-2AO Economy eligibility-marker schema."""

    for registration in INF2AO_PRODUCTION_OUTPUT_MARKET_ELIGIBILITY_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_construction_job_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the generic Construction plot-job event schemas."""

    for registration in CONSTRUCTION_JOB_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_construction_production_failure_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the owner-bound production failure event schema."""

    for registration in CONSTRUCTION_PRODUCTION_FAILURE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_construction_maintenance_obligation_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the owner-bound maintenance obligation event schema."""

    for registration in CONSTRUCTION_MAINTENANCE_OBLIGATION_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_construction_output_certification_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the owner-bound production output certification schema."""

    for registration in CONSTRUCTION_OUTPUT_CERTIFICATION_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_inventory_output_custody_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the Inventory-owned production output custody schema."""

    for registration in INVENTORY_OUTPUT_CUSTODY_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_construction_lifecycle_event_schemas(registry: EventSchemaRegistry) -> None:
    """Install the core Construction facility/run lifecycle schemas."""

    for registration in CONSTRUCTION_LIFECYCLE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc


def register_construction_production_event_schemas(registry: EventSchemaRegistry) -> None:
    """Register the complete opt-in Construction/Production event schema bundle."""

    register_construction_job_event_schemas(registry)
    register_construction_production_failure_event_schemas(registry)
    register_construction_maintenance_obligation_event_schemas(registry)
    register_construction_output_certification_event_schemas(registry)
    register_construction_lifecycle_event_schemas(registry)
    register_construction_maintenance_event_schemas(registry)
    register_inventory_output_custody_event_schemas(registry)


def register_construction_maintenance_event_schemas(registry: EventSchemaRegistry) -> None:
    """Register facility repair and maintenance-state event schemas."""

    for registration in CONSTRUCTION_MAINTENANCE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            existing = registry.get(registration.event_type, registration.schema_version)
            if existing != registration:
                raise exc
