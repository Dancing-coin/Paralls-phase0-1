from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
import json
import pickle
from typing import Protocol

from app.models.authority_event import AuthorityEvent


EventConsumer = Callable[[AuthorityEvent], None]


def authority_events_equal(left: AuthorityEvent, right: AuthorityEvent) -> bool:
    def canonical(event: AuthorityEvent) -> str:
        return json.dumps(
            event.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

    return canonical(left) == canonical(right)


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
    def __init__(self, *, now_ts_provider: Callable[[], int] | None = None,
                 history_limits: dict[str, int] | None = None) -> None:
        if any(isinstance(limit, bool) or limit < 1 for limit in (history_limits or {}).values()):
            raise ValueError("authority_history_limit_invalid")
        self._history_limits = dict(history_limits or {})
        self._events: dict[int, AuthorityEvent] = {}
        self._serialized_events: dict[int, bytes | None] = {}
        self._limited_event_ids: dict[str, deque[int]] = {
            event_type: deque() for event_type in self._history_limits
        }
        self._population_event_positions: dict[str, int] = {}
        self._next_position = 0
        self._subscribers: dict[str, list[tuple[str, EventConsumer]]] = {}
        self._now_ts_provider = now_ts_provider or (lambda: 0)

    def publish(self, event: AuthorityEvent) -> None:
        population_event = (
            event.event_type == "population_cadence_event"
            and event.durability == "realtime"
        )
        existing_position = (
            self._population_event_positions.get(event.event_id)
            if population_event
            else None
        )
        if existing_position is not None:
            stored = self._events[existing_position]
            serialized = self._serialized_events[existing_position]
            previous = pickle.loads(serialized) if serialized is not None else stored
            if not authority_events_equal(previous, event):
                raise ValueError("authority_event_id_conflict")
        else:
            serialized = (
                pickle.dumps(event, protocol=pickle.HIGHEST_PROTOCOL)
                if event.event_type == "population_cadence_event"
                and event.durability == "realtime"
                else None
            )
            stored = (
                event.model_copy(update={"payload": {}}).model_copy(deep=True)
                if serialized is not None
                else event.model_copy(deep=True)
            )
            position = self._next_position
            self._next_position += 1
            self._events[position] = stored
            self._serialized_events[position] = serialized
            if population_event:
                self._population_event_positions[event.event_id] = position
            limit = self._history_limits.get(event.event_type)
            if limit is not None:
                retained_ids = self._limited_event_ids[event.event_type]
                retained_ids.append(position)
                while len(retained_ids) > limit:
                    evicted_position = retained_ids.popleft()
                    evicted = self._events.pop(evicted_position, None)
                    self._serialized_events.pop(evicted_position, None)
                    if evicted is not None and evicted.event_type == "population_cadence_event":
                        if self._population_event_positions.get(evicted.event_id) == evicted_position:
                            self._population_event_positions.pop(evicted.event_id, None)
        subscribers = [
            *self._subscribers.get(event.event_type, []),
            *self._subscribers.get("*", []),
        ]
        for consumer_id, consumer in subscribers:
            if self._matches_route(stored, consumer_id):
                consumer(
                    pickle.loads(serialized)
                    if serialized is not None
                    else stored.model_copy(deep=True)
                )

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
        events = [
            (event, self._serialized_events[position])
            for position, event in self._events.items()
        ]
        if room_id is not None:
            events = [item for item in events if item[0].room_id == room_id]
        if event_type is not None:
            events = [item for item in events if item[0].event_type == event_type]
        events = [item for item in events if self._matches_route(item[0], consumer_id)]
        if not include_realtime:
            events = [item for item in events if item[0].durability != "realtime"]
        if current_only:
            events = [item for item in events if not self._is_expired(item[0])]
        return [
            pickle.loads(snapshot) if snapshot is not None else event.model_copy(deep=True)
            for event, snapshot in events
        ]

    def authority_recovery_ledger(self) -> AuthorityRecoveryLedger:
        return AuthorityRecoveryLedger(
            event_ids=frozenset(
                event.event_id for event in self._events.values()
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
