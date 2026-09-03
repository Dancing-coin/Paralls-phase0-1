from app.models.authority_event import AuthorityEvent
from app.models.siming_runtime_state import ObservedSimingEvent


class SimingObservePipeline:
    ALLOWED_EVENT_TYPES = {
        "world_fact_event",
        "visual_fact_event",
        "esm_result_event",
        "character_behavior_event",
        "conversation_resolution_event",
        "constraint_state_event",
        "population_cadence_event",
    }

    def observe(self, events: list[AuthorityEvent]) -> list[ObservedSimingEvent]:
        observed: list[ObservedSimingEvent] = []
        for event in events:
            if event.event_type not in self.ALLOWED_EVENT_TYPES:
                continue
            if not self._is_routed_to_siming(event):
                continue
            observed.append(ObservedSimingEvent.from_authority_event(event))
        return observed

    def _is_routed_to_siming(self, event: AuthorityEvent) -> bool:
        target_ids = {str(target_id) for target_id in event.routing.target_ids}
        if "siming" in target_ids:
            return True
        return event.routing.audience_mode == "broadcast"
