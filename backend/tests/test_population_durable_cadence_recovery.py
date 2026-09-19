from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.world import WorldContinuityRuntime
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.world_runtime.population_driver import PopulationCadenceDriver
from test_population_runtime_driver import _mode


def _runtime(path, actors=("one", "two")):
    world = WorldContinuityRuntime(store=DurableGameplayEventStore(path), mode=_mode(),
                                   roster=PopulationRoster(actor_ids=actors))
    if not world.store.get_stream_head("world:world"):
        assert world.resume().committed
    return world


def _publisher(world, bus):
    return RuntimeCadencePublisher(world_runtime=world, event_bus=bus,
                                   room_id="room", scene_id="scene", zone_id="zone")


@pytest.mark.parametrize("population", [2, 1000])
def test_publication_head_reads_do_not_scale_with_population(tmp_path, monkeypatch, population):
    from app.population_continuity.publication import publish_authorized_population_cadence

    world = _runtime(tmp_path / "gameplay.json", tuple(f"actor_{i}" for i in range(population)))
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    projections = world.build_population_projections(cadence)
    reads = []
    original = world.store.get_stream_head

    def read(ref):
        reads.append(ref)
        return original(ref)

    monkeypatch.setattr(world.store, "get_stream_head", read)
    bus = InMemoryAuthorityEventBus()
    arguments = dict(cadence=cadence, store=world.store, organization_projection={},
        population_projections=projections, event_bus=bus, room_id="room", scene_id="scene",
        zone_id="zone", causation_id="cause", correlation_id="corr")
    event = publish_authorized_population_cadence(**arguments)
    assert event is not None and len(event.payload["population_projections"]) == population
    # 同一个已确认 world pin 的数据库读取须为常数；所有角色仍完整校验和发布。
    assert len(reads) <= 4
    world.pause(reason="changed-after-publication")
    assert publish_authorized_population_cadence(**arguments) is None
    assert len(bus.list_events(include_realtime=True)) == 1


def test_publication_rechecks_heads_after_authorizer_callback(tmp_path):
    from app.population_continuity.publication import publish_authorized_population_cadence

    world = _runtime(tmp_path / "gameplay.json")
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    projections = world.build_population_projections(cadence)
    bus = InMemoryAuthorityEventBus()

    def authorize(_projection, **_):
        world.pause(reason="changed-during-authorization")
        return True

    assert publish_authorized_population_cadence(cadence=cadence, store=world.store,
        organization_projection={}, legacy_projections=projections[-1:],
        population_projections=projections[:-1], legacy_projection_authorizer=authorize,
        event_bus=bus, room_id="room", scene_id="scene", zone_id="zone",
        causation_id="cause", correlation_id="corr") is None
    assert not bus.list_events(include_realtime=True)


def test_append_before_delivery_and_restart_replays_pending_window(tmp_path):
    path = tmp_path / "gameplay.json"
    world = _runtime(path)
    bus = InMemoryAuthorityEventBus()

    def crash(_event):
        assert len(world.store.read_stream("population-cadence:world")) == 1
        raise RuntimeError("consumer_crash")

    bus.subscribe("population_cadence_event", crash)
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence) is None
    assert publisher.confirmed_tick == 0
    assert world.store.list_outbox(include_delivered=False)[0].attempt_count == 1
    restored_world = _runtime(path)
    restored_bus = InMemoryAuthorityEventBus()
    restored = _publisher(restored_world, restored_bus)
    assert restored.confirmed_tick == 0
    assert restored(cadence) is not None
    assert restored.confirmed_tick == 60
    assert len(restored_world.store.read_stream("population-cadence:world")) == 1
    assert not restored_world.store.list_outbox(include_delivered=False)
    assert restored_world.population_hot_state.read("one")["last_update_tick"] == 60
    assert restored(cadence) is not None
    assert len(restored_bus.list_events(include_realtime=True)) == 1


def test_pending_window_keeps_its_committed_source_after_world_head_changes(tmp_path):
    path = tmp_path / "gameplay.json"
    world = _runtime(path, ("one",))
    failing_bus = InMemoryAuthorityEventBus()
    failing_bus.subscribe(
        "population_cadence_event",
        lambda _: (_ for _ in ()).throw(RuntimeError("consumer_crash")),
    )
    publisher = _publisher(world, failing_bus)
    committed = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(committed) is None
    world.pause(reason="source-changed")
    world.resume()

    restored_world = _runtime(path, ("one",))
    restored = _publisher(restored_world, InMemoryAuthorityEventBus())
    current = restored_world.build_population_cadence(
        window_start=0,
        window_end=60,
        cadence_id=committed.cadence_id,
    )

    assert current.cadence_source_revision > committed.cadence_source_revision
    assert restored(current) is not None
    assert restored.confirmed_tick == 60
    assert restored_world.population_hot_state.read("one")["last_update_tick"] == 60


def test_delivered_restart_rebuilds_hot_rows_and_uses_tick_not_revision(tmp_path):
    path = tmp_path / "gameplay.json"
    world = _runtime(path)
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    for start in (0, 60, 120):
        assert publisher(world.build_population_cadence(window_start=start, window_end=start + 60))
    rows = world.population_hot_state.export_rows()
    restored_world = _runtime(path)
    restored = _publisher(restored_world, InMemoryAuthorityEventBus())
    assert restored.confirmed_tick == 180
    assert restored_world.population_hot_state.export_rows() == rows
    assert restored_world.store.get_stream_head("world:world") == 1
    assert not restored_world.store.list_outbox(include_delivered=False)


def test_compact_anchor_and_roster_mismatch_fail_closed(tmp_path):
    path = tmp_path / "gameplay.json"
    actors = tuple(f"actor_{i}" for i in range(1000))
    world = _runtime(path, actors)
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence)
    record = world.store.read_stream("population-cadence:world")[0]
    assert len(json.dumps(record.payload)) < 5000
    assert record.payload["authority_event"]["payload"]["population_projections"] == []
    with pytest.raises(ValueError, match="population_roster_mismatch"):
        _publisher(_runtime(path, ("changed",)), InMemoryAuthorityEventBus())
    with pytest.raises(ValueError, match="population_cadence_confirmation_conflict"):
        publisher(cadence.model_copy(update={"window_end": 61}))


@pytest.mark.parametrize(
    "update",
    [
        {"world_mode_ref": "world-mode:changed"},
        {"cadence_source_ref": "world:changed"},
        {"deterministic_seed": "seed:changed"},
        {"catch_up_limit": 99},
        {"budget": 99},
    ],
)
def test_same_cadence_id_rejects_changed_stable_semantics(tmp_path, update):
    world = _runtime(tmp_path / "gameplay.json")
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence)

    with pytest.raises(ValueError, match="population_cadence_confirmation_conflict"):
        publisher(cadence.model_copy(update=update))


def test_failed_append_leaves_hot_rows_and_cursor_unconfirmed(tmp_path, monkeypatch):
    world = _runtime(tmp_path / "gameplay.json")
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    before = world.population_hot_state.export_rows()
    original = world.store.append_batch

    def fail(batch):
        return original(batch.model_copy(update={"expected_stream_revisions": {publisher.stream_id: 99}}))

    monkeypatch.setattr(world.store, "append_batch", fail)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is None
    assert publisher.confirmed_tick == 0
    assert world.population_hot_state.export_rows() == before
    assert not world.store.read_stream(publisher.stream_id)


def test_hot_projection_failure_after_delivery_can_retry_without_redelivery(tmp_path, monkeypatch):
    world = _runtime(tmp_path / "gameplay.json")
    bus = InMemoryAuthorityEventBus()
    publisher = _publisher(world, bus)
    original = world.confirm_population_cadence
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    monkeypatch.setattr(world, "confirm_population_cadence", lambda _: (_ for _ in ()).throw(RuntimeError("hot_failure")))
    with pytest.raises(RuntimeError, match="hot_failure"):
        publisher(cadence)
    assert publisher.confirmed_tick == 0
    monkeypatch.setattr(world, "confirm_population_cadence", original)
    assert publisher(cadence)
    assert publisher.confirmed_tick == 60
    assert len(bus.list_events(include_realtime=True)) == 1


def test_delivered_restart_rejects_b0_rule_drift(tmp_path, monkeypatch):
    import app.population_continuity.world as world_module

    path = tmp_path / "gameplay.json"
    world = _runtime(path, ("one",))
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence)
    original = world_module.advance_b0_row

    def drift(**kwargs):
        result = original(**kwargs)
        values = dict(result.values)
        values["fatigue"] = round(min(1.0, float(values["fatigue"]) + 0.1), 9)
        return replace(result, values=MappingProxyType(values))

    monkeypatch.setattr(world_module, "advance_b0_row", drift)

    with pytest.raises(ValueError, match="population_cadence_projection_mismatch"):
        _publisher(_runtime(path, ("one",)), InMemoryAuthorityEventBus())


def test_delivered_hot_retry_revalidates_projection_before_confirm(tmp_path, monkeypatch):
    from app.population_continuity.runtime_publication import _digest

    world = _runtime(tmp_path / "gameplay.json", ("one",))
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    original = world.confirm_population_cadence
    monkeypatch.setattr(
        world,
        "confirm_population_cadence",
        lambda _: (_ for _ in ()).throw(RuntimeError("hot_failure")),
    )
    with pytest.raises(RuntimeError, match="hot_failure"):
        publisher(cadence)
    record = publisher._records[cadence.cadence_id]
    record["projection_digest"] = "sha256:changed-rule-output"
    record["record_digest"] = _digest(
        {key: value for key, value in record.items() if key != "record_digest"}
    )
    monkeypatch.setattr(world, "confirm_population_cadence", original)

    with pytest.raises(ValueError, match="population_cadence_projection_mismatch"):
        publisher(cadence)
    assert publisher.confirmed_tick == 0


def test_driver_reports_real_b0_and_due_processing(tmp_path):
    world = _runtime(tmp_path / "gameplay.json")
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publisher,
                                     window_size=21600, catch_up_limit=1)
    result = driver.tick(21600)
    assert result.b0_advanced_count == 2
    assert result.due_item_count == 2
    assert result.deferred_item_count == result.rejected_item_count == 0
    assert not world.due_population_work(21600)


def test_real_process_crash_recovers_committed_pending_window(tmp_path):
    script = '''
import os, sys
from app.gameplay.event_store import DurableGameplayEventStore
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.world import WorldContinuityRuntime
from app.population_continuity.runtime_publication import RuntimeCadencePublisher
from app.services.authority_event_bus import InMemoryAuthorityEventBus
mode = WorldModeProfile(world_ref="crash", mode="simulation", revision="mode:v1", cadence_class="hourly",
    batch_limit=3, wake_budget=3, catch_up_limit=2, degraded_threshold=20)
store = DurableGameplayEventStore(sys.argv[1])
world = WorldContinuityRuntime(store=store, mode=mode, roster=PopulationRoster(actor_ids=("one",)))
if not store.get_stream_head("world:crash"):
    world.resume()
bus = InMemoryAuthorityEventBus()
if sys.argv[2] == "crash":
    bus.subscribe("population_cadence_event", lambda event: os._exit(23))
publisher = RuntimeCadencePublisher(world_runtime=world, event_bus=bus, room_id="r", scene_id="s", zone_id="z")
cadence = world.build_population_cadence(window_start=0, window_end=60)
assert publisher(cadence)
assert publisher.confirmed_tick == 60
assert world.population_hot_state.read("one")["last_update_tick"] == 60
assert len(store.read_stream("population-cadence:crash")) == 1
assert not store.list_outbox(include_delivered=False)
print("recovered_exactly_one_window")
'''
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(root), str(root / "backend"))))
    path = str(tmp_path / "gameplay.json")
    first = subprocess.run([sys.executable, "-c", script, path, "crash"], cwd=root, env=env, capture_output=True, text=True)
    assert first.returncode == 23, first.stderr
    second = subprocess.run([sys.executable, "-c", script, path, "recover"], cwd=root, env=env, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr
    assert "recovered_exactly_one_window" in second.stdout
