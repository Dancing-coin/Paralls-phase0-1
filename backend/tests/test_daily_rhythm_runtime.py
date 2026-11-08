from app.gameplay.daily_rhythm_runtime import (
    DAILY_RHYTHM_EVENT_TYPES,
    DailyRhythmRuntime,
    create_daily_rhythm_event_schema_registry,
)
from app.gameplay.event_store import GameplayEventStore
from app.models.fact_type import FactType
from app.gameplay.event_schema_registry import EventSchemaRegistryError


def test_daily_rhythm_declares_fact_types_and_phase_machine():
    assert DAILY_RHYTHM_EVENT_TYPES == {
        "daily_rhythm.initialized",
        "daily_rhythm.state_updated",
    }
    assert FactType.from_event_type("daily_rhythm.fatigue_state") is FactType.DAILY_RHYTHM_FATIGUE_STATE
    assert DailyRhythmRuntime.phase_at(0) == "morning"
    assert DailyRhythmRuntime.phase_at(6 * 3_600) == "afternoon"
    assert DailyRhythmRuntime.phase_at(12 * 3_600) == "evening"
    assert DailyRhythmRuntime.phase_at(18 * 3_600) == "night"
    assert DailyRhythmRuntime.ACTIVITY_PHASE_MACHINE_ID == "daily_rhythm.activity_phase"
    assert DailyRhythmRuntime.activity_phase_states() == ("morning", "afternoon", "evening", "night")


def test_daily_rhythm_runtime_publishes_initialization_and_updates():
    class Bus:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event)

    bus = Bus()
    runtime = DailyRhythmRuntime(bus)
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.4, "activity_phase": "afternoon"}, tick=6 * 3_600, revision=1)
    assert [event.event_type for event in bus.events] == [
        "daily_rhythm.initialized",
        "daily_rhythm.state_updated",
    ]
    assert bus.events[-1].payload["fact_types"] == [
        "daily_rhythm.activity_phase_state",
        "daily_rhythm.fatigue_state",
    ]
    assert bus.events[0].payload["state"] == {
        "last_update_tick": 0,
        "activity_phase": "morning",
        "fatigue": 0.2,
        "need_pressure": 0.1,
        "next_due_tick": 21_600,
        "starvation_credit": 0.0,
    }


def test_daily_rhythm_owner_appends_fact_events_before_authority_publication():
    class Bus:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event)

    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    bus = Bus()
    runtime = DailyRhythmRuntime(bus, store=store)
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.3}, tick=1, revision=1)
    events = store.read_events()
    assert [event.event_type for event in events] == [
        "daily_rhythm.initialized",
        "daily_rhythm.state_updated",
    ]
    assert [event.event_id for event in bus.events] == [event.event_id for event in events]
    assert events[-1].payload["state"]["fatigue"] == 0.3


def test_daily_rhythm_schema_registry_rejects_unregistered_events():
    registry = create_daily_rhythm_event_schema_registry()
    assert registry.get("daily_rhythm.initialized", 1).schema_version == 1
    try:
        registry.require("daily_rhythm.unknown", 1)
    except EventSchemaRegistryError:
        pass
    else:
        raise AssertionError("unknown daily rhythm event was accepted")
