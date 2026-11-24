"""Place Machine events visible to the shared gameplay schema registry."""

from app.gameplay.event_schema_registry import (
    EventSchemaRegistration,
    EventSchemaRegistry,
    EventSchemaRegistryError,
)


PLACE_ASSESSMENT_CONFIRMED_EVENT = "gameplay.presence.place_passability_confirmed"

PLACE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.presence.place_passability_changed",
        1,
        "sha256:architecture-v2:place:passability-changed:v1",
    ),
    EventSchemaRegistration(
        PLACE_ASSESSMENT_CONFIRMED_EVENT,
        1,
        "sha256:architecture-v2:place:passability-confirmed:v1",
    ),
)


def register_place_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in PLACE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            if registry.get(registration.event_type, registration.schema_version) != registration:
                raise exc
