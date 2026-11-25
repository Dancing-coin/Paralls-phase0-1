from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from itertools import count

from app.contracts.owner_fact_query import FactTypeValue, OwnerProjection
from app.gameplay.event_store import GameplayEventStore
from app.models.authority_event import AuthorityEvent
from app.models.fact_type import FACT_TYPE_REGISTRY, FactType, FactTypeRef, FactTypeRegistry


class OwnerFactQueryImpl:
    """Read the latest declared facts from their committed owner streams."""

    _ids = count(1)
    _AUDIENCE_VISIBILITY = {
        "siming_internal": frozenset({"project", "authority_only"}),
        "public": frozenset({"public"}),
    }

    def __init__(
        self,
        event_store: GameplayEventStore,
        fact_type_registry: FactTypeRegistry = FACT_TYPE_REGISTRY,
        *,
        event_bus=None,
    ) -> None:
        self._store = event_store
        self._registry = fact_type_registry
        self._event_bus = event_bus
        self._subscriptions: dict[str, tuple[frozenset[str], Callable, str]] = {}
        self._bus_event_types: set[str] = set()

    def query_facts(
        self,
        fact_types: Iterable[FactTypeValue],
        *,
        actor_refs: Iterable[str] | None = None,
        at_revision: int | None = None,
        source_event_ref: str | None = None,
        audience: str = "siming_internal",
    ) -> list[OwnerProjection]:
        requested = tuple(dict.fromkeys(self._require_fact_type(value) for value in fact_types))
        if at_revision is not None and (type(at_revision) is not int or at_revision < 0):
            raise ValueError("owner_fact_revision_invalid")
        visible = self._AUDIENCE_VISIBILITY.get(audience)
        if visible is None:
            raise ValueError("owner_fact_audience_invalid")
        actors = None if actor_refs is None else frozenset(actor_refs)
        latest: dict[tuple[str, str], OwnerProjection] = {}
        owners_by_fact_actor: dict[tuple[str, str], str] = {}
        if source_event_ref is not None:
            try:
                event = self._store.get_event(source_event_ref)
            except KeyError:
                return []
            events_by_id = {event.event_id: event}
        elif actors is not None and requested and all(
            self._registry.domain_for(fact_type) == "daily_rhythm" for fact_type in requested
        ):
            events_by_id = {
                event.event_id: event
                for actor_ref in actors
                for event in self._store.read_stream(f"daily-rhythm:{actor_ref}")
            }
        else:
            event_types = {fact_type.value for fact_type in requested}
            if any(self._registry.domain_for(fact_type) == "daily_rhythm" for fact_type in requested):
                event_types.update({"daily_rhythm.initialized", "daily_rhythm.state_updated"})
            events_by_id = {
                event.event_id: event
                for event_type in event_types
                for event in self._store.read_events(event_type=event_type)
            }
        for event in sorted(events_by_id.values(), key=lambda item: item.global_sequence):
            stream_id = event.stream_id
            payload = event.payload
            actor_ref = str(payload.get("actor_ref") or payload.get("actor_id") or "")
            if actors is not None and actor_ref not in actors:
                continue
            if event.visibility_policy not in visible:
                continue
            source_owner = self._store.transaction_principal(event.transaction_id)
            if source_owner is None:
                raise ValueError("owner_fact_transaction_missing")
            declared = payload.get("fact_types", ())
            declared_types = (
                frozenset(item for item in declared if isinstance(item, str))
                if isinstance(declared, (list, tuple)) else frozenset()
            )
            for fact_type in requested:
                if event.event_type != fact_type.value and fact_type.value not in declared_types:
                    continue
                revision = payload.get(
                    "revision",
                    0 if event.event_type.endswith(".initialized") else event.stream_revision,
                )
                if type(revision) is not int or revision < 0:
                    raise ValueError("owner_fact_revision_invalid")
                if at_revision is not None and revision > at_revision:
                    continue
                fact_payload = self._payload_for_fact(fact_type, payload)
                key = (fact_type.value, actor_ref)
                previous_owner = owners_by_fact_actor.get(key)
                if previous_owner is not None and previous_owner != source_owner:
                    raise ValueError(f"owner_fact_owner_conflict:{fact_type.value}:{actor_ref}")
                owners_by_fact_actor[key] = source_owner
                projection = OwnerProjection(
                    fact_type=fact_type,
                    actor_ref=actor_ref,
                    revision=revision,
                    source_owner=source_owner,
                    source_event_ref=event.event_id,
                    event_type=event.event_type,
                    causation_id=event.causation_id,
                    correlation_id=event.correlation_id,
                    captured_at=self._captured_at(payload, event.global_sequence),
                    freshness=(
                        "live"
                        if event.stream_revision == self._store.get_stream_head(stream_id)
                        else "stale"
                    ),
                    payload=fact_payload,
                )
                if key not in latest or latest[key].revision <= revision:
                    latest[key] = projection
        return [latest[key] for key in sorted(latest)]

    def get_owner_for_fact_type(self, fact_type: FactTypeValue) -> str:
        registered = self._require_fact_type(fact_type)
        projections = self.query_facts([registered])
        owners = {projection.source_owner for projection in projections}
        if len(owners) != 1:
            reason = "unavailable" if not owners else "ambiguous"
            raise ValueError(f"owner_fact_owner_{reason}:{registered.value}")
        return next(iter(owners))

    def subscribe(
        self,
        fact_types: Iterable[FactTypeValue],
        callback: Callable[[OwnerProjection], None],
        *,
        audience: str = "siming_internal",
    ) -> str:
        requested = frozenset(self._require_fact_type(value).value for value in fact_types)
        if not requested or not callable(callback) or audience not in self._AUDIENCE_VISIBILITY:
            raise ValueError("owner_fact_subscription_invalid")
        subscription_id = f"owner-fact-subscription:{next(self._ids)}"
        self._subscriptions[subscription_id] = (requested, callback, audience)
        if self._event_bus is not None:
            for event_type in {"daily_rhythm.initialized", "daily_rhythm.state_updated", *requested}:
                if event_type not in self._bus_event_types:
                    self._event_bus.subscribe(event_type, self._on_event, consumer_id="owner_fact_query")
                    self._bus_event_types.add(event_type)
        return subscription_id

    def _on_event(self, event: AuthorityEvent) -> None:
        for fact_types, callback, audience in tuple(self._subscriptions.values()):
            declared = event.payload.get("fact_types", ())
            changed = set(declared) if isinstance(declared, (list, tuple)) else set()
            if event.event_type in fact_types or fact_types.intersection(changed):
                projections = self.query_facts(
                    (FactType(value) if FactType.from_event_type(value) is not None else self._registry.from_event_type(value)
                     for value in fact_types.intersection(changed | {event.event_type})),
                    actor_refs=[event.source.actor_id] if event.source.actor_id else None,
                    audience=audience,
                )
                for projection in projections:
                    callback(projection)

    def _require_fact_type(self, fact_type: FactTypeValue) -> FactTypeValue:
        value = fact_type.value if isinstance(fact_type, (FactType, FactTypeRef)) else ""
        registered = self._registry.from_event_type(value)
        if registered is None:
            raise ValueError(f"owner_fact_type_unregistered:{value}")
        return registered

    @staticmethod
    def _payload_for_fact(fact_type: FactTypeValue, event_payload: dict[str, object]) -> dict[str, object]:
        state = event_payload.get("state")
        suffix = fact_type.value.removeprefix("daily_rhythm.")
        field = suffix.removesuffix("_state")
        if isinstance(state, Mapping) and field in state:
            return {field: state[field]}
        return dict(state) if isinstance(state, Mapping) else dict(event_payload)

    @staticmethod
    def _captured_at(payload: dict[str, object], fallback: int) -> int:
        for key in ("captured_at", "tick", "producer_ts"):
            value = payload.get(key)
            if type(value) is int and value >= 0:
                return value
        return fallback
