"""Event schema registrations for the Facility-owned gate latch machine."""

from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry


GATE_LATCH_EVENT = "gameplay.machine.transitioned"
FACILITY_GATE_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        GATE_LATCH_EVENT,
        1,
        "sha256:facility:machine-transitioned:v1",
    ),
)


def register_facility_gate_event_schemas(registry: EventSchemaRegistry) -> None:
    for registration in FACILITY_GATE_EVENT_SCHEMAS:
        try:
            registry.register(registration)
        except ValueError:
            if registry.get(registration.event_type, registration.schema_version) != registration:
                raise
