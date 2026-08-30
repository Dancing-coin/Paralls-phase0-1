from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput


class SimingEventConsumer:
    ALLOWED_EVENT_TYPES = {
        "world_fact_event",
        "visual_fact_event",
        "esm_result_event",
        "character_behavior_event",
        "conversation_resolution_event",
        "constraint_state_event",
        "siming_staging_ack",
        "population_cadence_event",
    }

    def handle_event(self, event: AuthorityEvent) -> list[SimingInput]:
        if event.event_type not in self.ALLOWED_EVENT_TYPES:
            return []
        input_type = "population_cadence_input" if event.event_type == "population_cadence_event" else event.event_type
        return [SimingInput(input_type=input_type, source_event=event)]
