from app.models.authority_event import AuthorityEvent
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType, FactTypeRef
from app.models.siming_runtime_state import ObservedSimingEvent


class SimingObservePipeline:
    """S2: observe registered fact types after startup coverage validation.

    Phase 2: replace aggregate visibility with Owner-declared visibility contracts.
    """

    def __init__(self) -> None:
        FACT_TYPE_REGISTRY.validate_event_type_coverage()

    @staticmethod
    def get_observed_fact_types() -> frozenset[FactType | FactTypeRef]:
        return frozenset(
            fact_type
            for event_type in FACT_TYPE_REGISTRY.event_types()
            if (fact_type := FACT_TYPE_REGISTRY.from_event_type(event_type)) is not None
        )

    ALLOWED_FACT_TYPES = get_observed_fact_types.__func__()
    def observe(self, events: list[AuthorityEvent]) -> list[ObservedSimingEvent]:
        observed: list[ObservedSimingEvent] = []
        for event in events:
            fact_type = FACT_TYPE_REGISTRY.from_event_type(event.event_type)
            if fact_type not in self.ALLOWED_FACT_TYPES and not isinstance(fact_type, FactTypeRef):
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
