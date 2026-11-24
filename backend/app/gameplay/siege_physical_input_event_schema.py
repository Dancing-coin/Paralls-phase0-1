"""Schema registrations for authenticated siege physics evidence."""

from app.gameplay.event_schema_registry import (
    EventSchemaRegistration,
    EventSchemaRegistry,
)


GATE_IMPACT_INPUT_EVENT = "gameplay.facility.gate_impact_input_received"
GATE_IMPACT_INPUT_EVENT_V2 = "gameplay.facility.gate_impact_input_received@2"
PRESENCE_ASSESSMENT_INPUT_EVENT = "gameplay.presence.assessment_input_received"
PRESENCE_ASSESSMENT_INPUT_EVENT_V2 = "gameplay.presence.assessment_input_received@2"

SIEGE_PHYSICAL_INPUT_EVENT_SCHEMAS = (
    EventSchemaRegistration(
        GATE_IMPACT_INPUT_EVENT,
        1,
        "sha256:paralls-siege-gate-impact-input-v1",
    ),
    EventSchemaRegistration(
        GATE_IMPACT_INPUT_EVENT_V2,
        1,
        "sha256:paralls-siege-gate-impact-input-v2",
    ),
    EventSchemaRegistration(
        PRESENCE_ASSESSMENT_INPUT_EVENT,
        1,
        "sha256:paralls-siege-presence-assessment-input-v1",
    ),
    EventSchemaRegistration(
        PRESENCE_ASSESSMENT_INPUT_EVENT_V2,
        1,
        "sha256:paralls-siege-presence-assessment-input-v2",
    ),
)


def register_siege_physical_input_event_schemas(
    registry: EventSchemaRegistry,
) -> None:
    for registration in SIEGE_PHYSICAL_INPUT_EVENT_SCHEMAS:
        registry.register(registration)
