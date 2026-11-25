"""Holdings event schemas declared for runtime validation and graph discovery."""

from app.gameplay.event_schema_registry import (
    EventSchemaRegistration,
    EventSchemaRegistry,
    EventSchemaRegistryError,
)

HOLDINGS_EVENT_TYPES = (
    "gameplay.holdings.lot_created",
    "gameplay.holdings.reserved",
    "gameplay.holdings.transferred",
    "gameplay.holdings.consumed",
    "gameplay.holdings.split",
    "gameplay.holdings.merged",
    "gameplay.holdings.lost",
    "gameplay.holdings.reservation_released",
    "gameplay.holdings.reservation_settled",
    "gameplay.holdings.reservation_transferred",
)

HOLDINGS_EVENT_SCHEMAS = tuple(
    EventSchemaRegistration(
        event_type, 1, f"sha256:architecture-v2:holdings:{event_type}:v1",
    )
    for event_type in HOLDINGS_EVENT_TYPES
)


def register_holdings_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in HOLDINGS_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            if registry.get(registration.event_type, registration.schema_version) != registration:
                raise exc
