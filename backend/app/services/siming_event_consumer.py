from app.models.authority_event import AuthorityEvent
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType
from app.models.siming_event import SimingInput


class SimingEventConsumer:
    ALLOWED_FACT_TYPES = frozenset({
        FactType.WORLD_FACT,
        FactType.VISUAL_FACT,
        FactType.ESM_RESULT,
        FactType.CHARACTER_BEHAVIOR,
        FactType.CONVERSATION_RESOLUTION,
        FactType.CONSTRAINT_STATE,
        FactType.POPULATION_CADENCE,
    })
    # Compatibility surface for callers that still enumerate subscription keys.
    ALLOWED_EVENT_TYPES = frozenset((*ALLOWED_FACT_TYPES, "siming_staging_ack"))

    def handle_event(self, event: AuthorityEvent) -> list[SimingInput]:
        fact_type = FACT_TYPE_REGISTRY.from_event_type(event.event_type)
        if event.event_type != "siming_staging_ack" and fact_type not in self.ALLOWED_FACT_TYPES:
            return []
        input_type = "population_cadence_input" if event.event_type == "population_cadence_event" else event.event_type
        return [SimingInput(input_type=input_type, source_event=event)]
