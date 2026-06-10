from app.models.authority_event import AuthorityEvent


FRONTEND_AUTHORITY_EVENT_TYPES = {
    "siming.visual_observability_request",
    "siming.fact_reveal",
}


def project_authority_event_for_frontend(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in FRONTEND_AUTHORITY_EVENT_TYPES:
        return None
    return {
        "message_type": "authority_event",
        "payload": event.model_dump(exclude_none=True),
    }


def project_authority_event_as_siming_output(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in FRONTEND_AUTHORITY_EVENT_TYPES:
        return None

    payload = {
        "room_id": event.room_id,
        "output_type": "attention_prompt",
        "causation_id": event.causation_id,
        "correlation_id": event.correlation_id,
        "producer_ts": event.producer_ts,
        "target_actor_id": event.payload.get("target_actor_id"),
        "target_environment_id": event.payload.get("target_environment_id"),
        "target_object_id": event.payload.get("target_object_id"),
        "prompt_summary": str(event.payload.get("presentation_hint", "notice established visual fact")),
        "authority_event_id": event.event_id,
        "authority_event_type": event.event_type,
    }
    return {
        "message_type": "siming_output",
        "payload": payload,
    }


class FrontendAuthorityEventProjector:
    def __init__(self) -> None:
        self._pending: list[dict[str, object]] = []

    def handle_event(self, event: AuthorityEvent) -> None:
        envelope = project_authority_event_as_siming_output(event)
        if envelope is not None:
            self._pending.append(envelope)

    def drain(self) -> list[dict[str, object]]:
        pending = self._pending
        self._pending = []
        return pending

    def clear(self) -> None:
        self._pending = []
