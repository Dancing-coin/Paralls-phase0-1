import pytest

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


def test_publish_state_with_six_fields():
    class Bus:
        def __init__(self):
            self.events = []

        def publish(self, event):
            self.events.append(event)

    bus = Bus()
    DailyRhythmRuntime(bus).publish_state(
        "actor:a",
        {
            "fatigue": 0.4,
            "need_pressure": 0.2,
            "starvation_credit": 0.1,
            "activity_phase": "afternoon",
            "next_due_tick": 21_600,
            "last_update_tick": 100,
        },
        tick=100,
        revision=1,
    )

    assert bus.events[0].payload["fact_types"] == [
        "daily_rhythm.activity_phase_state",
        "daily_rhythm.fatigue_state",
        "daily_rhythm.last_update_tick",
        "daily_rhythm.need_pressure_state",
        "daily_rhythm.next_due_tick",
        "daily_rhythm.starvation_credit_state",
    ]
    assert FactType.from_event_type("daily_rhythm.next_due_tick") is FactType.DAILY_RHYTHM_NEXT_DUE_TICK
    assert FactType.from_event_type("daily_rhythm.last_update_tick") is FactType.DAILY_RHYTHM_LAST_UPDATE_TICK


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


def test_population_window_commits_actor_updates_in_one_owner_transaction():
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(None, store=store)
    updates = (("actor:a", {"fatigue": 0.3}, 1, 0, 0), ("actor:b", {"fatigue": 0.4}, 1, 0, 0))

    runtime.publish_population_window("cadence:1", updates, tick=1)
    runtime.publish_population_window("cadence:1", updates, tick=1)

    events = store.read_events()
    assert len(events) == 2
    assert len({event.transaction_id for event in events}) == 1
    assert {event.stream_id for event in events} == {"daily-rhythm:actor:a", "daily-rhythm:actor:b"}


def test_population_window_does_not_reuse_an_unrelated_owner_event():
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(None, store=store)
    runtime.initialize("actor:a")
    payload = runtime._state_payload("actor:a", {"fatigue": 0.3}, 1, 1)
    from app.gameplay.settlement_plan import build_atomic_event_batch

    unrelated = build_atomic_event_batch(
        command_id="unrelated-owner-command",
        principal_ref=runtime.PRINCIPAL_REF,
        stream_id="daily-rhythm:actor:a",
        expected_revision=store.get_stream_head("daily-rhythm:actor:a"),
        event_specs=(("daily_rhythm.state_updated", payload),),
        idempotency_key="unrelated-owner-command",
        causation_id="unrelated-owner-command",
        correlation_id="unrelated-owner-command",
    )
    assert store.append_batch(unrelated).committed

    with pytest.raises(ValueError, match="hot_state_revision_conflict"):
        runtime.publish_population_window(
            "cadence:1", (("actor:a", {"fatigue": 0.3}, 1, 0, 1),), tick=1
        )


def test_daily_rhythm_schema_registry_rejects_unregistered_events():
    registry = create_daily_rhythm_event_schema_registry()
    assert registry.get("daily_rhythm.initialized", 1).schema_version == 1
    try:
        registry.require("daily_rhythm.unknown", 1)
    except EventSchemaRegistryError:
        pass
    else:
        raise AssertionError("unknown daily rhythm event was accepted")


def test_population_window_retries_all_bus_fanout_after_partial_failure():
    class Bus:
        def __init__(self):
            self.events = []
            self.failed_once = False

        def publish(self, event):
            self.events.append(event)
            if event.event_type == "daily_rhythm.state_updated" and event.source.actor_id == "actor:a" and not self.failed_once:
                self.failed_once = True
                raise RuntimeError("subscriber_failed_once")

    bus = Bus()
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(bus, store=store)
    runtime.initialize("actor:a")
    runtime.initialize("actor:b")
    updates = (("actor:a", {"fatigue": 0.3}, 1, 0, 1), ("actor:b", {"fatigue": 0.4}, 1, 0, 1))

    with pytest.raises(RuntimeError, match="subscriber_failed_once"):
        runtime.publish_population_window("cadence:retry", updates, tick=1)

    runtime.publish_population_window("cadence:retry", updates, tick=1)

    assert [event.source.actor_id for event in bus.events if event.event_type == "daily_rhythm.state_updated"].count("actor:a") == 2
    assert [event.source.actor_id for event in bus.events if event.event_type == "daily_rhythm.state_updated"].count("actor:b") == 2
    assert len(store.read_events(event_type="daily_rhythm.state_updated")) == 2

def test_single_state_publication_rejects_non_sequential_logical_revision():
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(None, store=store)
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.4}, tick=10, revision=1)

    with pytest.raises(ValueError, match="daily_rhythm_revision_conflict"):
        runtime.publish_state("actor:a", {"fatigue": 0.5}, tick=20, revision=1)

def test_single_state_publication_rejects_changed_payload_for_reused_revision_key():
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(None, store=store)
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.4}, tick=10, revision=1)

    with pytest.raises(ValueError, match="daily_rhythm_revision_conflict"):
        runtime.publish_state("actor:a", {"fatigue": 0.9}, tick=10, revision=1)

def test_single_state_publication_replays_committed_event_after_bus_failure():
    class Bus:
        def __init__(self):
            self.events = []
            self.failed = False

        def publish(self, event):
            self.events.append(event)
            if event.event_type == "daily_rhythm.state_updated" and not self.failed:
                self.failed = True
                raise RuntimeError("bus_failure")

    bus = Bus()
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(bus, store=store)
    runtime.initialize("actor:a")

    with pytest.raises(RuntimeError, match="bus_failure"):
        runtime.publish_state("actor:a", {"fatigue": 0.6}, tick=10, revision=1)

    runtime.publish_state("actor:a", {"fatigue": 0.6}, tick=10, revision=1)

    assert len(store.read_stream("daily-rhythm:actor:a")) == 2
    assert [event.event_type for event in bus.events].count("daily_rhythm.state_updated") == 2


def test_concurrent_state_updates_cannot_commit_the_same_logical_revision(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())
    runtime = DailyRhythmRuntime(None, store=store)
    runtime.initialize("actor:a")
    first_waiting = Event()
    allow_first = Event()
    second_completed = Event()
    original_publish = runtime._publish

    def controlled_publish(event_type, actor_id, payload, room_id, scene_id, zone_id, *, expected_revision=None):
        if payload.get("tick") == 10:
            first_waiting.set()
            assert allow_first.wait(timeout=5)
        try:
            return original_publish(event_type, actor_id, payload, room_id, scene_id, zone_id,
                                    expected_revision=expected_revision)
        finally:
            if payload.get("tick") == 11:
                second_completed.set()

    monkeypatch.setattr(runtime, "_publish", controlled_publish)

    def publish(tick, fatigue):
        try:
            runtime.publish_state("actor:a", {"fatigue": fatigue}, tick=tick, revision=1)
            return "committed"
        except ValueError as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(publish, 10, 0.4)
        assert first_waiting.wait(timeout=5)
        second = pool.submit(publish, 11, 0.6)
        assert second_completed.wait(timeout=5)
        allow_first.set()
        results = (first.result(timeout=5), second.result(timeout=5))

    assert results.count("committed") == 1
    assert results.count("daily_rhythm_owner_append_rejected") == 1
    assert len(store.read_stream("daily-rhythm:actor:a")) == 2
