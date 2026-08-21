from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from app.models.authority_event import AuthorityEvent


EventConsumer = Callable[[AuthorityEvent], None]


@dataclass(frozen=True)
class AuthorityRecoveryLedger:
    event_ids: frozenset[str]
    is_complete_across_restart: bool


class AuthorityEventBusPort(Protocol):
    def publish(self, event: AuthorityEvent) -> None:
        raise NotImplementedError

    def subscribe(self, event_type: str, consumer: EventConsumer, *, consumer_id: str = "*") -> None:
        raise NotImplementedError

    def list_events(
        self,
        *,
        room_id: str | None = None,
        event_type: str | None = None,
        consumer_id: str = "*",
        include_realtime: bool = False,
        current_only: bool = True,
    ) -> list[AuthorityEvent]:
        raise NotImplementedError

    def authority_recovery_ledger(self) -> AuthorityRecoveryLedger:
        raise NotImplementedError


class InMemoryAuthorityEventBus:
    def __init__(self, *, now_ts_provider: Callable[[], int] | None = None) -> None:
        self._events: list[AuthorityEvent] = []
        self._subscribers: dict[str, list[tuple[str, EventConsumer]]] = {}
        self._now_ts_provider = now_ts_provider or (lambda: 0)

    def publish(self, event: AuthorityEvent) -> None:
        stored = event.model_copy(deep=True)
        self._events.append(stored)
        for consumer_id, consumer in self._subscribers.get(event.event_type, []):
            if self._matches_route(stored, consumer_id):
                consumer(stored.model_copy(deep=True))

    def subscribe(self, event_type: str, consumer: EventConsumer, *, consumer_id: str = "*") -> None:
        self._subscribers.setdefault(event_type, []).append((consumer_id, consumer))

    def list_events(
        self,
        *,
        room_id: str | None = None,
        event_type: str | None = None,
        consumer_id: str = "*",
        include_realtime: bool = False,
        current_only: bool = True,
    ) -> list[AuthorityEvent]:
        events = self._events
        if room_id is not None:
            events = [event for event in events if event.room_id == room_id]
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        events = [event for event in events if self._matches_route(event, consumer_id)]
        if not include_realtime:
            events = [event for event in events if event.durability != "realtime"]
        if current_only:
            events = [event for event in events if not self._is_expired(event)]
        return [event.model_copy(deep=True) for event in events]

    def authority_recovery_ledger(self) -> AuthorityRecoveryLedger:
        return AuthorityRecoveryLedger(
            event_ids=frozenset(
                event.event_id
                for event in self.list_events(
                    include_realtime=True,
                    current_only=False,
                )
            ),
            is_complete_across_restart=False,
        )

    def _matches_route(self, event: AuthorityEvent, consumer_id: str) -> bool:
        if consumer_id == "*":
            return True
        if event.routing.audience_mode in {"broadcast", "authority_broadcast"}:
            return True
        return consumer_id in set(event.routing.target_ids)

    def _is_expired(self, event: AuthorityEvent) -> bool:
        if event.ttl is None:
            return False
        return self._now_ts_provider() > event.producer_ts + event.ttl
