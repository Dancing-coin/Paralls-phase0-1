from app.gameplay.daily_rhythm_runtime import (
    DailyRhythmRuntime,
    create_daily_rhythm_event_schema_registry,
)
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.daily_rhythm_projection import DailyRhythmProjection


def make_projection() -> tuple[GameplayEventStore, DailyRhythmRuntime, DailyRhythmProjection]:
    store = GameplayEventStore(event_schema_registry=create_daily_rhythm_event_schema_registry())

    class Bus:
        def publish(self, _event):
            pass

    return store, DailyRhythmRuntime(Bus(), store=store), DailyRhythmProjection(store)


def test_rebuild_from_empty_stream():
    _store, _runtime, projection = make_projection()

    assert projection.rebuild("actor:a") == projection._default_state()
    assert projection.get_revision("actor:a") == 0


def test_rebuild_from_three_events():
    _store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.4}, tick=10, revision=1)
    runtime.publish_state("actor:a", {"need_pressure": 0.3}, tick=20, revision=2)

    state = projection.rebuild("actor:a")

    assert state["fatigue"] == 0.4
    assert state["need_pressure"] == 0.3
    assert state["last_update_tick"] == 0
    assert projection.get_revision("actor:a") == 2


def test_read_with_cache():
    store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    original_read_stream = store.read_stream
    reads = 0

    def counted_read_stream(*args, **kwargs):
        nonlocal reads
        reads += 1
        return original_read_stream(*args, **kwargs)

    store.read_stream = counted_read_stream
    projection.read("actor:a")
    projection.read("actor:a")

    assert reads == 1


def test_read_with_refresh():
    _store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    assert projection.read("actor:a")["fatigue"] == 0.2
    runtime.publish_state("actor:a", {"fatigue": 0.6}, tick=10, revision=1)

    assert projection.read("actor:a")["fatigue"] == 0.6


def test_get_revision():
    _store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.6}, tick=10, revision=1)

    projection.rebuild("actor:a")

    assert projection.get_revision("actor:a") == 1


def test_until_revision():
    _store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.6}, tick=10, revision=1)

    assert projection.rebuild("actor:a", until_revision=0)["fatigue"] == 0.2
    assert projection.get_revision("actor:a") == 0


def test_multiple_actors():
    _store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    runtime.initialize("actor:b")
    runtime.publish_state("actor:a", {"fatigue": 0.7}, tick=10, revision=1)

    assert projection.rebuild("actor:a")["fatigue"] == 0.7
    assert projection.rebuild("actor:b")["fatigue"] == 0.2


def test_default_state():
    _store, _runtime, projection = make_projection()

    assert projection.read("actor:missing") == {
        "fatigue": 0.2,
        "need_pressure": 0.1,
        "starvation_credit": 0.0,
        "activity_phase": "morning",
        "next_due_tick": 21_600,
        "last_update_tick": 0,
    }


def test_refresh_reads_only_new_stream_events():
    store, runtime, projection = make_projection()
    runtime.initialize("actor:a")
    runtime.publish_state("actor:a", {"fatigue": 0.4}, tick=10, revision=1)
    projection.read("actor:a")
    runtime.publish_state("actor:a", {"need_pressure": 0.3}, tick=20, revision=2)
    original_read = store.read_stream
    reads = []

    def counted_read(stream_id, **kwargs):
        reads.append(kwargs.get("from_revision", 1))
        return original_read(stream_id, **kwargs)

    store.read_stream = counted_read
    state = projection.read("actor:a")

    assert state["fatigue"] == 0.4
    assert state["need_pressure"] == 0.3
    assert projection.get_revision("actor:a") == 2
    assert reads == [3]
