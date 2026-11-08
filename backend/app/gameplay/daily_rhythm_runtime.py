from __future__ import annotations

from typing import Mapping

from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.event_store import GameplayEventStore
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.fact_type import FactType


DAILY_RHYTHM_EVENT_TYPES = {"daily_rhythm.initialized", "daily_rhythm.state_updated"}
_STATE_FACT_FIELDS = {
    "fatigue": FactType.DAILY_RHYTHM_FATIGUE_STATE,
    "need_pressure": FactType.DAILY_RHYTHM_NEED_PRESSURE_STATE,
    "starvation_credit": FactType.DAILY_RHYTHM_STARVATION_CREDIT_STATE,
    "activity_phase": FactType.DAILY_RHYTHM_ACTIVITY_PHASE_STATE,
}


def create_daily_rhythm_event_schema_registry() -> EventSchemaRegistry:
    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("daily_rhythm.initialized", 1, "sha256:daily-rhythm:initialized:v1"))
    registry.register(EventSchemaRegistration("daily_rhythm.state_updated", 1, "sha256:daily-rhythm:state-updated:v1"))
    return registry


class DailyRhythmRuntime:
    """Publishes the B0 daily rhythm state owned by this domain."""

    ACTIVITY_PHASE_MACHINE_ID = "daily_rhythm.activity_phase"
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
        facts = sorted(_STATE_FACT_FIELDS[field].value for field in values if field in _STATE_FACT_FIELDS)
        self._publish("daily_rhythm.state_updated", actor_id, {"actor_id": actor_id, "tick": tick, "revision": revision, "state": dict(values), "fact_types": facts}, room_id, scene_id, zone_id)

    def _publish(self, event_type: str, actor_id: str, payload: dict[str, object], room_id: str, scene_id: str, zone_id: str) -> None:
        event_id = f"{event_type}:{actor_id}:{payload.get('tick', 0)}:{payload.get('revision', 0)}"
        if self._store is not None:
            stream_id = f"daily-rhythm:{actor_id}"
            command_id = event_id
            existing = self._store.get_by_idempotency("daily_rhythm_runtime", event_id)
            if existing is not None and existing.committed and existing.committed_event_ids:
                return
            batch = build_atomic_event_batch(
                command_id=command_id,
                principal_ref="daily_rhythm_runtime",
                stream_id=stream_id,
                expected_revision=self._store.get_stream_head(stream_id),
                event_specs=((event_type, payload),),
                idempotency_key=event_id,
                causation_id=f"daily_rhythm:{actor_id}:{payload.get('tick', 0)}",
                correlation_id=f"daily_rhythm:{actor_id}",
            )
            result = self._store.append_batch(batch)
            if not result.committed:
                raise ValueError("daily_rhythm_owner_append_rejected")
            stored = self._store.get_event(result.committed_event_ids[0])
            event_id = stored.event_id
        self._event_bus.publish(AuthorityEvent(
            event_id=event_id,
            event_type=event_type,
            producer_ts=int(payload.get("tick", 0)),
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            source=AuthorityEventSource(layer="gameplay", system="daily_rhythm_runtime", actor_id=actor_id),
            routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="domain", target_ids=[]),
            priority="p2",
            ttl=None,
            durability="replayable",
            causation_id=f"daily_rhythm:{actor_id}:{payload.get('tick', 0)}",
            correlation_id=f"daily_rhythm:{actor_id}",
            payload=payload,
        ))


__all__ = ["DAILY_RHYTHM_EVENT_TYPES", "DailyRhythmRuntime", "create_daily_rhythm_event_schema_registry"]
