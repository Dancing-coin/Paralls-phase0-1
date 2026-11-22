"""Pool event types declared for graph visibility discovery."""

from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry, EventSchemaRegistryError

POOL_EVENT_TYPES = (
    "gameplay.pool.initialized",
    "gameplay.pool.adjusted",
    "gameplay.pool.reserved",
    "gameplay.pool.released",
    "gameplay.pool.consumed",
    "gameplay.pool.bound_changed",
    "gameplay.pool.threshold_crossed",
)

POOL_EVENT_SCHEMAS = tuple(
    EventSchemaRegistration(
        event_type,
        1,
        f"sha256:architecture-v2:pool:{event_type}:v1",
    )
    for event_type in POOL_EVENT_TYPES
)


def register_pool_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in POOL_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except EventSchemaRegistryError as exc:
            if registry.get(registration.event_type, registration.schema_version) != registration:
                raise exc
