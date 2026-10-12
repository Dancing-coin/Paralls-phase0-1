from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from contextlib import contextmanager
from contextvars import ContextVar
import json
import pickle
from typing import Protocol
from types import FunctionType, MethodType

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource


EventConsumer = Callable[[AuthorityEvent], None]
_PREPARED_DELIVERY = ContextVar('authority_prepared_delivery', default=None)


@contextmanager
def _prepared_delivery_scope(event, snapshot, receiver):
    delivery = [event, snapshot, receiver]
    token = _PREPARED_DELIVERY.set(delivery)
    try:
        yield
    finally:
        # 任务可能复制 context；退出时同步撤销所有副本中的借用资格及强引用。
        delivery[:] = [None, None, None]
        _PREPARED_DELIVERY.reset(token)


def _prepared_delivery_snapshot(event, receiver, expected_code):
    current = _PREPARED_DELIVERY.get()
    if current is None or current[0] is not event:
        return None
    actual = current[2]
    if type(receiver) is MethodType and type(actual) is MethodType:
        if receiver.__self__ is not actual.__self__ or receiver.__func__ is not actual.__func__:
            return None
        function = receiver.__func__
    elif type(receiver) is FunctionType and receiver is actual:
        function = receiver
    else:
        return None
    if (function.__code__ is not expected_code or type(current[1]) is not bytes
            or pickle.dumps is not _NATIVE_PICKLE_DUMPS or pickle.loads is not _NATIVE_PICKLE_LOADS
            or not _native_snapshot_models(event)
            or any(getattr(function, '__code__', None) is not code for function, code in _NATIVE_SNAPSHOT_CODES)
            or not _plain_population_metadata(event)):
        return None
    return current[1]


def _plain_population_metadata(event):
    # 原生 JSON 投影片段之外的元数据也不能带入自定义 pickle 回调。
    if type(event.payload) is not dict or any(type(key) is not str for key in event.payload):
        return False
    pending = [value for key, value in event.payload.items() if key != 'population_projections']
    pending.extend(value for key, value in event.__dict__.items() if key not in ('payload', 'source', 'routing'))
    pending.extend(event.source.__dict__.values())
    pending.extend(event.routing.__dict__.values())
    seen = set()
    remaining = 256
    while pending:
        remaining -= 1
        if remaining < 0:
            return False
        value = pending.pop()
        if type(value) in (str, int, float, bool, type(None)):
            continue
        if type(value) not in (dict, list):
            return False
        if id(value) in seen:
            continue
        seen.add(id(value))
        if type(value) is dict:
            if any(type(key) is not str for key in value):
                return False
            pending.extend(value.values())
        else:
            pending.extend(value)
    return True


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

    def subscribe(self, event_type: str, consumer: EventConsumer, *, consumer_id: str = "*",
                  excluded_event_types: frozenset[str] = frozenset()) -> None:
        raise NotImplementedError

    def list_events(
        self,
        *,
        room_id: str | None = None,
        event_type: str | None = None,
        consumer_id: str = "*",
        include_realtime: bool = False,
        current_only: bool = True,
        after_cursor: int | None = None,
    ) -> list[AuthorityEvent]:
        raise NotImplementedError

    def cursor(self) -> int:
        raise NotImplementedError

    def event_counts(self) -> dict[str, int]:
        raise NotImplementedError

    def authority_recovery_ledger(self) -> AuthorityRecoveryLedger:
        raise NotImplementedError


class InMemoryAuthorityEventBus:
    def __init__(self, *, now_ts_provider: Callable[[], int] | None = None,
                 history_limits: dict[str, int] | None = None,
                 default_history_limit: int | None = None) -> None:
        limits = (*((history_limits or {}).values()), default_history_limit)
        if any(limit is not None and (isinstance(limit, bool) or limit < 1) for limit in limits):
            raise ValueError("authority_history_limit_invalid")
        self._history_limits = dict(history_limits or {})
        self._default_history_limit = default_history_limit
        self._events: dict[int, AuthorityEvent] = {}
        self._serialized_events: dict[int, bytes | None] = {}
        self._limited_event_ids: dict[str, deque[int]] = {
            event_type: deque() for event_type in self._history_limits
        }
        self._population_event_positions: dict[str, int] = {}
        self._next_position = 0
        self._subscribers: dict[str, list[tuple[str, EventConsumer, frozenset[str]]]] = {}
        self._now_ts_provider = now_ts_provider or (lambda: 0)
        self._prepared_subscribers: list[tuple[EventConsumer, Callable]] = []

    def publish(self, event: AuthorityEvent) -> None:
        self._publish(event, frame=None)

    def _publish_prepared_population(self, event: AuthorityEvent, frame) -> None:
        publish = self.publish
        if (type(self) is not InMemoryAuthorityEventBus or type(publish) is not MethodType
                or publish.__func__ is not _NATIVE_PUBLISH
                or type(self._publish) is not MethodType or self._publish.__func__ is not _NATIVE_PUBLISH_BODY
                or pickle.dumps is not _NATIVE_PICKLE_DUMPS or pickle.loads is not _NATIVE_PICKLE_LOADS
                or not _native_snapshot_models(event)
                or event.event_type != "population_cadence_event" or event.durability != "realtime"):
            return self.publish(event)
        self._publish(event, frame=frame)

    def _subscribe_prepared_population(self, consumer: EventConsumer, prepared_consumer: Callable) -> None:
        self.subscribe("population_cadence_event", consumer)
        self._prepared_subscribers.append((consumer, prepared_consumer))

    def _publish(self, event: AuthorityEvent, *, frame) -> None:
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
            # 同 ID 重投继续使用原快照，不能配上新帧。
            frame = None
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
            limit = self._history_limits.get(event.event_type, self._default_history_limit)
            if limit is not None:
                retained_ids = self._limited_event_ids.setdefault(event.event_type, deque())
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
        for consumer_id, consumer, excluded_event_types in subscribers:
            if stored.event_type not in excluded_event_types and self._matches_route(stored, consumer_id):
                decoder = pickle.loads
                native_snapshot = frame is not None and _native_snapshot_models(stored)
                received = (
                    decoder(serialized)
                    if serialized is not None
                    else stored.model_copy(deep=True)
                )
                prepared_consumer = next((prepared for original, prepared in self._prepared_subscribers
                    if consumer is original), None) if (native_snapshot
                        and decoder is _NATIVE_PICKLE_LOADS and pickle.dumps is _NATIVE_PICKLE_DUMPS
                        and _native_snapshot_models(received)) else None
                if prepared_consumer is None:
                    consumer(received)
                else:
                    # 仅在实际首发回调内借用字节；其他 forwarder 不能冒充原生接收者。
                    with _prepared_delivery_scope(received, serialized, prepared_consumer):
                        prepared_consumer(received, frame)

    def subscribe(self, event_type: str, consumer: EventConsumer, *, consumer_id: str = "*",
                  excluded_event_types: frozenset[str] = frozenset()) -> None:
        self._subscribers.setdefault(event_type, []).append((consumer_id, consumer, frozenset(excluded_event_types)))

    def cursor(self) -> int:
        return self._next_position

    def event_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self._events.values():
            counts[event.event_type] = counts.get(event.event_type, 0) + 1
        return counts

    def list_events(
        self,
        *,
        room_id: str | None = None,
        event_type: str | None = None,
        consumer_id: str = "*",
        include_realtime: bool = False,
        current_only: bool = True,
        after_cursor: int | None = None,
    ) -> list[AuthorityEvent]:
        if after_cursor is not None and (
            isinstance(after_cursor, bool) or after_cursor < 0
        ):
            raise ValueError("authority_event_cursor_invalid")
        events = [
            (event, self._serialized_events[position])
            for position, event in self._events.items()
            if after_cursor is None or position >= after_cursor
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


_NATIVE_PUBLISH = InMemoryAuthorityEventBus.publish
_NATIVE_PUBLISH_BODY = InMemoryAuthorityEventBus._publish
_NATIVE_PICKLE_DUMPS = pickle.dumps
_NATIVE_PICKLE_LOADS = pickle.loads
_NATIVE_SNAPSHOT_BINDINGS = tuple((model, tuple((name, getattr(model, name))
    for name in ("__getstate__", "__setstate__", "__reduce__", "__reduce_ex__", "model_copy", "__copy__", "__deepcopy__")))
    for model in (AuthorityEvent, AuthorityEventSource, AuthorityEventRouting))
_NATIVE_SNAPSHOT_CODES = tuple((function, getattr(function, '__code__', None))
    for function in dict.fromkeys(function for _, bindings in _NATIVE_SNAPSHOT_BINDINGS for _, function in bindings))


def _native_snapshot_models(event: AuthorityEvent) -> bool:
    # codec 原生并不代表模型快照钩子原生；检查实际解码前后的模型绑定。
    return all(type(value) is model and all(getattr(model, name) is function and name not in value.__dict__
        for name, function in bindings)
        for value, (model, bindings) in zip((event, event.source, event.routing), _NATIVE_SNAPSHOT_BINDINGS, strict=True))
