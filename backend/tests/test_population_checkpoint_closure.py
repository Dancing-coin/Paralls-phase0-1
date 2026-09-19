from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from test_siming_population_authorized_cadence_publication import _cadence, _commit, _store


@pytest.fixture(autouse=True)
def initialized_runtime():
    from app import main

    main.reset_runtime_state()
    yield
    main.close_runtime_resources()


def _publish(main, store, *, window=1, extra_pins=None):
    cadence = _cadence().model_copy(update={
        "cadence_id": f"cadence:closure:{window}", "window_start": window, "window_end": window + 1,
        "base_revision_vector": {**_cadence().base_revision_vector, **(extra_pins or {})},
    })
    return main.publish_authorized_population_cadence(
        cadence=cadence, store=store,
        organization_projection={"organization_ref": "org:test", "scope": "organization:summary",
                                 "source_revision_vector": dict(cadence.base_revision_vector)},
        room_id="room:test", scene_id="scene:test", zone_id="zone:test",
        causation_id=f"cause:{window}", correlation_id=f"correlation:{window}",
    )


def test_production_publisher_restores_checkpoint_and_reads_only_tail(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
    store = _store()
    assert _publish(main, store) is not None
    restored = GameplayEventStore.from_snapshot(store.export_snapshot())
    _commit(restored, event_id="private:tail", event_type="test.private", stream_id="private:test",
            payload={}, visibility_policy="actor:self")
    reads = []
    original = restored.read_events

    def counted(**kwargs):
        result = original(**kwargs)
        reads.append((kwargs, len(result)))
        return result

    monkeypatch.setattr(restored, "read_events", counted)
    assert _publish(main, restored, window=2) is not None
    assert reads == [({"global_sequence_after": 1, "limit": 1}, 1)]
    checkpoints = restored.list_projection_checkpoints(projector_id="population-continuity")
    assert len(checkpoints) == 1
    assert checkpoints[0].last_global_sequence == 2


def test_population_source_tail_pages_before_visibility_filtering(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
    store = _store()
    assert _publish(main, store) is not None
    for index in range(300):
        _commit(store, event_id=f"private:page:{index}", event_type="test.private", stream_id="private:paged",
                payload={}, visibility_policy="actor:self")
    reads = []
    original = store.read_events

    def read(**kwargs):
        assert 0 < kwargs.get("limit", 0) <= 256
        result = original(**kwargs)
        reads.append((kwargs["global_sequence_after"], len(result)))
        return result

    monkeypatch.setattr(store, "read_events", read)
    assert _publish(main, store, window=2) is not None
    assert reads == [(1, 256), (257, 44)]
    assert store.list_projection_checkpoints(projector_id="population-continuity")[0].last_global_sequence == 301


@pytest.mark.parametrize("corruption", ["hash", "cursor", "scope"])
def test_publisher_rejects_corrupt_checkpoint_without_publishing(monkeypatch, corruption):
    from app import main

    bus = InMemoryAuthorityEventBus()
    monkeypatch.setattr(main, "authority_event_bus", bus)
    store = _store()
    assert _publish(main, store) is not None
    checkpoints = store.list_projection_checkpoints(projector_id="population-continuity")
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    if corruption == "hash":
        checkpoint = checkpoint.model_copy(update={"projection_hash": "sha256:corrupted"})
    elif corruption == "cursor":
        checkpoint = checkpoint.model_copy(update={"last_global_sequence": 100})
    else:
        state = {**checkpoint.state, "report_scope": "actor:self"}
        checkpoint = checkpoint.model_copy(update={"state": state})
    store.save_projection_checkpoint(checkpoint)
    with pytest.raises(ValueError, match="projection_checkpoint|projection_gap"):
        _publish(main, store, window=2)
    assert len(bus.list_events(include_realtime=True, current_only=False)) == 1


def test_checkpoint_applies_same_stream_replacement_and_visibility_revocation(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
    store = _store()
    stream = "gameplay:social:population:signal:test"
    for revision, visibility in ((1, "public"), (2, "public"), (3, "actor:self")):
        _commit(store, event_id=f"signal:{revision}",
                event_type="gameplay.social.population_signal_recorded@1", stream_id=stream,
                payload={"signal_ref": f"signal:{revision}", "provenance_ref": f"evidence:{revision}",
                         "materialization_state": "proposed", "visibility_scope": visibility},
                visibility_policy=visibility)
        event = _publish(main, store, window=revision, extra_pins={stream: revision})
        assert event is not None
        projections = event.payload["population_projections"]
        if visibility == "public":
            assert len(projections) == 1
            assert projections[0]["revision_vector"] == {stream: revision}
        else:
            assert projections == []
    checkpoints = store.list_projection_checkpoints(projector_id="population-continuity")
    assert len(checkpoints) == 1
    assert checkpoints[0].last_global_sequence == 4


def test_gap_inside_tail_is_rejected_before_visibility_filtering(monkeypatch):
    from app import main

    monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
    store = _store()
    assert _publish(main, store) is not None
    for index in range(3):
        _commit(store, event_id=f"gap:{index}", event_type="test.unrelated", stream_id="test:gap",
                payload={}, visibility_policy="actor:self")
    original = store.read_events

    def missing_middle(**kwargs):
        return [event for event in original(**kwargs) if event.global_sequence != 3]

    monkeypatch.setattr(store, "read_events", missing_middle)
    with pytest.raises(ValueError, match="projection_gap"):
        _publish(main, store, window=2)


def test_durable_publisher_checkpoint_survives_process_reopen(tmp_path, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "authority_event_bus", InMemoryAuthorityEventBus())
    path = tmp_path / "gameplay.json"
    _store().save_snapshot(path)
    store = DurableGameplayEventStore(path)
    assert _publish(main, store) is not None
    reopened = DurableGameplayEventStore(path)
    checkpoints = reopened.list_projection_checkpoints(projector_id="population-continuity")
    assert len(checkpoints) == 1
    assert checkpoints[0].last_global_sequence == 1


@pytest.mark.asyncio
async def test_production_driver_constructs_cadence_once_per_window(monkeypatch):
    from app import main
    from app.population_continuity.world import WorldContinuityRuntime

    main.stop_population_runtime()
    main.reset_runtime_state()
    calls = []
    original = WorldContinuityRuntime.build_population_cadence

    def counted(self, **kwargs):
        calls.append(kwargs)
        return original(self, **kwargs)

    async def stop_after_window(seconds):
        main._population_runtime_stop_event.set()

    monkeypatch.setattr(WorldContinuityRuntime, "build_population_cadence", counted)
    monkeypatch.setattr(main, "_population_runtime_sleep", stop_after_window)
    try:
        await main.start_population_runtime()
        assert len(calls) == 1
    finally:
        await main._shutdown_population_runtime()
