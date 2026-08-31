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
