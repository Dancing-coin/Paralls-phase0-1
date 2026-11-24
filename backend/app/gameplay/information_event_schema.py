from __future__ import annotations

from app.gameplay.event_schema_registry import (
    EventSchemaRegistration,
    EventSchemaRegistry,
    EventSchemaRegistryError,
)


INFORMATION_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        "gameplay.information.knowledge_updated@1",
        1,
        "sha256:information:knowledge-updated:v1",
    ),
)


def register_information_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in INFORMATION_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError:
            if registry.get(registration.event_type, registration.schema_version) != registration:
                raise
