from collections.abc import Callable
from typing import Protocol

from app.models.authority_event import AuthorityEvent


EventConsumer = Callable[[AuthorityEvent], None]


class AuthorityEventBusPort(Protocol):
    def publish(self, event: AuthorityEvent) -> None:
        raise NotImplementedError

    def subscribe(self, event_type: str, consumer: EventConsumer) -> None:
        raise NotImplementedError

    def list_events(self, *, room_id: str | None = None, event_type: str | None = None) -> list[AuthorityEvent]:
        raise NotImplementedError


class InMemoryAuthorityEventBus:
    def __init__(self) -> None:
        self._events: list[AuthorityEvent] = []
        self._subscribers: dict[str, list[EventConsumer]] = {}

    def publish(self, event: AuthorityEvent) -> None:
        stored = event.model_copy(deep=True)
        self._events.append(stored)
        for consumer in self._subscribers.get(event.event_type, []):
            consumer(stored.model_copy(deep=True))

    def subscribe(self, event_type: str, consumer: EventConsumer) -> None:
        self._subscribers.setdefault(event_type, []).append(consumer)

    def list_events(self, *, room_id: str | None = None, event_type: str | None = None) -> list[AuthorityEvent]:
        events = self._events
        if room_id is not None:
            events = [event for event in events if event.room_id == room_id]
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        return [event.model_copy(deep=True) for event in events]
