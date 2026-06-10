from app.models.authority_event import AuthorityEvent


FRONTEND_AUTHORITY_EVENT_TYPES = {
    "siming.visual_observability_request",
}


def project_authority_event_for_frontend(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type not in FRONTEND_AUTHORITY_EVENT_TYPES:
        return None
    return {
        "message_type": "authority_event",
        "payload": event.model_dump(exclude_none=True),
    }


class FrontendAuthorityEventProjector:
    def __init__(self) -> None:
        self._pending: list[dict[str, object]] = []

    def handle_event(self, event: AuthorityEvent) -> None:
        envelope = project_authority_event_for_frontend(event)
        if envelope is not None:
            self._pending.append(envelope)

    def drain(self) -> list[dict[str, object]]:
        pending = self._pending
        self._pending = []
        return pending

    def clear(self) -> None:
        self._pending = []
