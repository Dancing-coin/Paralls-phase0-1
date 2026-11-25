from __future__ import annotations

from typing import Mapping

from app.contracts.owner_registry import OWNER_REGISTRY
from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry
from app.gameplay.models import GameplayEvent
from app.gameplay.settlement_plan import build_atomic_event_batch, build_multi_stream_atomic_event_batch
from app.gameplay.event_store import GameplayEventStore
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.fact_type import FactType


DAILY_RHYTHM_EVENT_TYPES = {"daily_rhythm.initialized", "daily_rhythm.state_updated"}
_STATE_FACT_FIELDS = {
    "fatigue": FactType.DAILY_RHYTHM_FATIGUE_STATE,
    "need_pressure": FactType.DAILY_RHYTHM_NEED_PRESSURE_STATE,
    "starvation_credit": FactType.DAILY_RHYTHM_STARVATION_CREDIT_STATE,
    "activity_phase": FactType.DAILY_RHYTHM_ACTIVITY_PHASE_STATE,
    "next_due_tick": FactType.DAILY_RHYTHM_NEXT_DUE_TICK,
    "last_update_tick": FactType.DAILY_RHYTHM_LAST_UPDATE_TICK,
}


def create_daily_rhythm_event_schema_registry(registry: EventSchemaRegistry | None = None) -> EventSchemaRegistry:
    registry = registry or EventSchemaRegistry()
    registrations = (
        EventSchemaRegistration("daily_rhythm.initialized", 1, "sha256:daily-rhythm:initialized:v1"),
        EventSchemaRegistration("daily_rhythm.state_updated", 1, "sha256:daily-rhythm:state-updated:v1"),
    )
    for registration in registrations:
        try:
            registry.get(registration.event_type, registration.schema_version)
        except ValueError:
            registry.register(registration)
    return registry


class DailyRhythmRuntime:
    """Publishes the B0 daily rhythm state owned by this domain."""

    ACTIVITY_PHASE_MACHINE_ID = "daily_rhythm.activity_phase"
    PRINCIPAL_REF = OWNER_REGISTRY.get("daily_rhythm_runtime").principal_ref
    _ACTIVITY_PHASE_STATES = ("morning", "afternoon", "evening", "night")

    @classmethod
    def activity_phase_states(cls) -> tuple[str, ...]:
        return cls._ACTIVITY_PHASE_STATES

    def __init__(self, event_bus, *, store: GameplayEventStore | None = None) -> None:
        self._event_bus = event_bus
        self._store = store

    @staticmethod
    def phase_at(tick: int) -> str:
        local = tick % 86_400
        if local < 6 * 3_600:
            return "morning"
        if local < 12 * 3_600:
            return "afternoon"
        if local < 18 * 3_600:
            return "evening"
        return "night"

    def initialize(self, actor_id: str, *, room_id: str = "room:population", scene_id: str = "scene:population", zone_id: str = "zone:population", tick: int = 0) -> None:
        state = {"last_update_tick": tick, "activity_phase": self.phase_at(tick), "fatigue": 0.2,
                 "need_pressure": 0.1, "next_due_tick": 21_600, "starvation_credit": 0.0}
        self._publish("daily_rhythm.initialized", actor_id, {"actor_id": actor_id, "tick": tick, "state": state,
                                                              "fact_types": sorted(fact.value for fact in _STATE_FACT_FIELDS.values())}, room_id, scene_id, zone_id)

    def publish_state(self, actor_id: str, values: Mapping[str, object], *, tick: int, revision: int, room_id: str = "room:population", scene_id: str = "scene:population", zone_id: str = "zone:population") -> None:
        payload = self._state_payload(actor_id, values, tick, revision)
        expected_stream_revision = None
        if self._store is not None:
            event_id = f"daily_rhythm.state_updated:{actor_id}:{tick}:{revision}"
            previous = self._store.get_by_idempotency(self.PRINCIPAL_REF, event_id)
            if previous is not None and previous.committed:
                committed = self._store.get_transaction(previous.transaction_id)
                if (committed is not None and len(committed.events) == 1
                        and committed.events[0].event_type == "daily_rhythm.state_updated"
                        and committed.events[0].payload == payload):
                    self._publish_authority(
                        committed.events[0].event_id,
                        committed.events[0].event_type,
                        actor_id,
                        payload,
                        room_id,
                        scene_id,
                        zone_id,
                    )
                    return
                raise ValueError("daily_rhythm_revision_conflict")
            history = self._store.read_stream(f"daily-rhythm:{actor_id}")
            expected_stream_revision = history[-1].stream_revision if history else 0
            state_updates = [event for event in history if event.event_type == "daily_rhythm.state_updated"]
            previous_revision = state_updates[-1].payload.get("revision", 0) if state_updates else 0
            if (type(previous_revision) is not int or previous_revision < 0
                    or type(revision) is not int or revision <= 0 or revision != previous_revision + 1):
                raise ValueError("daily_rhythm_revision_conflict")
        self._publish("daily_rhythm.state_updated", actor_id, payload, room_id, scene_id, zone_id,
                      expected_revision=expected_stream_revision)

    @staticmethod
    def _state_payload(actor_id: str, values: Mapping[str, object], tick: int, revision: int) -> dict[str, object]:
        facts = sorted(_STATE_FACT_FIELDS[field].value for field in values if field in _STATE_FACT_FIELDS)
        return {"actor_id": actor_id, "tick": tick, "revision": revision, "state": dict(values), "fact_types": facts}

    def publish_population_window(
        self, cadence_id: str,
        updates: tuple[tuple[str, Mapping[str, object], int, int, int], ...], *, tick: int,
    ) -> tuple[GameplayEvent, ...]:
        if not updates:
            return ()
        store = self._store
        if store is None:
            raise ValueError("daily_rhythm_store_required")
        command_id = f"daily-rhythm-window:{cadence_id}"
        event_type = "daily_rhythm.state_updated"
        revisions = {f"daily-rhythm:{actor_id}": source_revision
                     for actor_id, _, _, _logical_revision, source_revision in updates}
        specs = {
            f"daily-rhythm:{actor_id}": ((event_type, self._state_payload(actor_id, values, tick, revision)),)
            for actor_id, values, revision, _logical_revision, _source_revision in updates
        }
        if len(revisions) != len(updates):
            raise ValueError("daily_rhythm_window_duplicate_actor")
        if any(revision != expected_revision + 1
               for _actor_id, _values, revision, expected_revision, _source_revision in updates):
            raise ValueError("daily_rhythm_revision_conflict")
        batch = build_multi_stream_atomic_event_batch(
            command_id=command_id, principal_ref=self.PRINCIPAL_REF, expected_revisions=revisions,
            event_specs=specs, idempotency_key=command_id, causation_id=command_id, correlation_id=command_id,
        )
        receipt = store.append_batch(batch)
        if receipt.committed and receipt.idempotency_status == "new_commit":
            first_sequence = receipt.global_sequence_range[0]
            events = tuple(event.model_copy(update={
                "stream_revision": receipt.resulting_stream_revisions[event.stream_id],
                "global_sequence": first_sequence + index,
            }) for index, event in enumerate(batch.events))
            self._publish_population_events(events)
            return events
        # A pre-v2 window may already have committed these facts individually.
        events = []
        for stream_id, ((_, payload),) in specs.items():
            source_revision = revisions[stream_id] + 1
            stored = store.read_stream(stream_id, from_revision=source_revision, to_revision=source_revision)
            legacy_command_id = (
                f"{event_type}:{payload['actor_id']}:{payload['tick']}:{payload['revision']}"
            )
            if (not stored or stored[0].event_type != event_type or stored[0].payload != payload
                    or stored[0].command_id not in {command_id, legacy_command_id}
                    or not store.transaction_owns_event(transaction_id=stored[0].transaction_id,
                                                        event_id=stored[0].event_id, principal_ref=self.PRINCIPAL_REF)):
                raise ValueError("hot_state_revision_conflict")
            events.append(stored[0])
        committed_events = tuple(events)
        self._publish_population_events(committed_events)
        return committed_events

    def _publish_population_events(self, events: tuple[GameplayEvent, ...]) -> None:
        if self._event_bus is None:
            return
        first_error: Exception | None = None
        for event in events:
            try:
                self._publish_authority(
                    event.event_id,
                    event.event_type,
                    str(event.payload["actor_id"]),
                    event.payload,
                    "room:population",
                    "scene:population",
                    "zone:population",
                )
            except Exception as exc:
                if first_error is None:
                    first_error = exc
        if first_error is not None:
            raise first_error

    def _publish(self, event_type: str, actor_id: str, payload: dict[str, object], room_id: str,
                 scene_id: str, zone_id: str, *, expected_revision: int | None = None) -> None:
        event_id = f"{event_type}:{actor_id}:{payload.get('tick', 0)}:{payload.get('revision', 0)}"
        if self._store is not None:
            stream_id = f"daily-rhythm:{actor_id}"
            command_id = event_id
            existing = self._store.get_by_idempotency(self.PRINCIPAL_REF, event_id)
            if existing is not None and existing.committed and existing.committed_event_ids:
                transaction = self._store.get_transaction(existing.transaction_id)
                if (transaction is None or len(transaction.events) != 1
                        or transaction.events[0].event_type != event_type
                        or transaction.events[0].payload != payload):
                    raise ValueError("daily_rhythm_event_conflict")
                self._publish_authority(
                    transaction.events[0].event_id, event_type, actor_id, payload, room_id, scene_id, zone_id
                )
                return
            batch = build_atomic_event_batch(
                command_id=command_id,
                principal_ref=self.PRINCIPAL_REF,
                stream_id=stream_id,
                expected_revision=(self._store.get_stream_head(stream_id)
                                   if expected_revision is None else expected_revision),
                event_specs=((event_type, payload),),
                idempotency_key=event_id,
                causation_id=f"daily_rhythm:{actor_id}:{payload.get('tick', 0)}",
                correlation_id=f"daily_rhythm:{actor_id}",
            )
            result = self._store.append_batch(batch)
            if not result.committed:
                raise ValueError("daily_rhythm_owner_append_rejected")
            event_id = result.committed_event_ids[0]
        self._publish_authority(event_id, event_type, actor_id, payload, room_id, scene_id, zone_id)

    def _publish_authority(self, event_id: str, event_type: str, actor_id: str, payload: dict[str, object],
                           room_id: str, scene_id: str, zone_id: str) -> None:
        if self._event_bus is not None:
            self._event_bus.publish(AuthorityEvent(
                event_id=event_id,
                event_type=event_type,
                producer_ts=int(payload.get("tick", 0)),
                room_id=room_id,
                scene_id=scene_id,
                zone_id=zone_id,
                source=AuthorityEventSource(layer="gameplay", system=self.PRINCIPAL_REF, actor_id=actor_id),
                routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="domain", target_ids=[]),
                priority="p2",
                ttl=None,
                durability="replayable",
                causation_id=f"daily_rhythm:{actor_id}:{payload.get('tick', 0)}",
                correlation_id=f"daily_rhythm:{actor_id}",
                payload=payload,
            ))


__all__ = ["DAILY_RHYTHM_EVENT_TYPES", "DailyRhythmRuntime", "create_daily_rhythm_event_schema_registry"]
