from app.models.authority_event import AuthorityEvent
from app.models.fact_type import FACT_TYPE_REGISTRY
from app.models.siming_event import SimingInput


def _registered_fact_types():
    return frozenset(
        fact_type
        for event_type in FACT_TYPE_REGISTRY.event_types()
        if (fact_type := FACT_TYPE_REGISTRY.from_event_type(event_type)) is not None
    )


class SimingEventConsumer:
    ALLOWED_FACT_TYPES = _registered_fact_types()
    # Compatibility surface for callers that still enumerate subscription keys.
    PROTOCOL_EVENT_TYPES = frozenset({"esm.feasibility_response", "esm.constraint_state"})
    ALLOWED_EVENT_TYPES = frozenset((*ALLOWED_FACT_TYPES, "siming_staging_ack", *PROTOCOL_EVENT_TYPES))

    def handle_event(self, event: AuthorityEvent) -> list[SimingInput]:
        fact_type = FACT_TYPE_REGISTRY.from_event_type(event.event_type)
        if event.event_type not in {"siming_staging_ack", *self.PROTOCOL_EVENT_TYPES} and fact_type not in self.ALLOWED_FACT_TYPES:
            return []
        input_type = "population_cadence_input" if event.event_type == "population_cadence_event" else event.event_type
        return [SimingInput(input_type=input_type, source_event=event)]
