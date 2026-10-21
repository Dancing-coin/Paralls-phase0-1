"""同次首发只编码一次，去重快照仍表示处理前的独立输入。"""
import cProfile
from contextlib import nullcontext
from contextvars import copy_context
import gc
import pickle
from types import FunctionType
import weakref

import pytest

from test_siming_prepared_population import case
from app.services.siming_event_pipeline import SimingEventPipeline


_original_ingress_handler = None
_snapshot_words = []


class SnapshotWord(str):
    def __reduce__(self):
        _snapshot_words.append(str(self))
        return SnapshotWord, (str(self),)


def changed_ingress_handler(self, event):
    event.correlation_id = 'changed-handler-code'
    return _original_ingress_handler(self, event)


def changed_snapshot_state(self):
    if type(self) is _snapshot_hook_event_type:
        _snapshot_hook_calls.append(id(self))
    return _snapshot_hook_original(self)


def pickle_dump_count(profiler):
    return sum(item.callcount for item in profiler.getstats()
               if item.code == '<built-in method _pickle.dumps>')


def test_native_prepared_ingress_encodes_once_and_preserves_conflict_check(tmp_path):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    finally:
        profiler.disable()
    assert event is not None and publisher.confirmed_tick == 60
    assert pickle_dump_count(profiler) == 1
    assert len(capability.read_sets) == 1
    stored = pickle.loads(pipeline._handled_events[event.event_id])
    assert stored.model_dump(mode='json') == event.model_dump(mode='json')
    pipeline.handle_event(event.model_copy(deep=True))
    assert len(capability.read_sets) == 1
    changed = event.model_copy(deep=True)
    changed.payload['extension'] = 'changed-after-success'
    with pytest.raises(ValueError, match='siming_event_id_conflict'):
        pipeline.handle_event(changed)
    assert 'extension' not in pickle.loads(pipeline._handled_events[event.event_id]).payload
    world.store.close()


def test_custom_prepared_forwarder_snapshots_actual_changed_input(tmp_path):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    original, prepared = bus._prepared_subscribers[0]

    def forward(event, frame):
        event.correlation_id = 'changed-before-prepared'
        return prepared(event, frame)

    bus._prepared_subscribers[0] = (original, forward)
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    assert event is not None
    stored = pickle.loads(pipeline._handled_events[event.event_id])
    assert stored.correlation_id == 'changed-before-prepared'
    assert event.correlation_id != stored.correlation_id
    world.store.close()


def test_native_main_receiver_reuses_snapshot_and_keeps_real_population_result():
    from app import main

    main.stop_population_runtime()
    main.reset_runtime_state()
    try:
        driver = main._build_population_driver()
        assert driver is not None
        cursor = main.authority_event_bus.cursor()
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            result = driver.tick(driver.current_tick + driver.window_size)
        finally:
            profiler.disable()
        assert not result.rejected_windows
        assert pickle_dump_count(profiler) == 1
        events = main.authority_event_bus.list_events(event_type='population_cadence_event', include_realtime=True,
            after_cursor=cursor)
        assert len(events) == 1
        stored = pickle.loads(main.siming_event_pipeline._handled_events[events[0].event_id])
        assert stored.model_dump(mode='json') == events[0].model_dump(mode='json')
    finally:
        main.stop_population_runtime()
        main.reset_runtime_state()


def test_changed_ingress_code_keeps_the_actual_snapshot(tmp_path, monkeypatch):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    function = SimingEventPipeline.handle_event
    original = FunctionType(function.__code__, function.__globals__, function.__name__,
        function.__defaults__, function.__closure__)
    monkeypatch.setitem(function.__globals__, '_original_ingress_handler', original)
    monkeypatch.setattr(function, '__code__', changed_ingress_handler.__code__)
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    assert event is not None
    stored = pickle.loads(pipeline._handled_events[event.event_id])
    assert stored.correlation_id == 'changed-handler-code'
    assert event.correlation_id != stored.correlation_id
    world.store.close()


def test_failed_prepared_delivery_does_not_retain_received_event(tmp_path, monkeypatch):
    from app.population_continuity.siming_contracts import PopulationCadenceInput

    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    received = []

    def fail(cls, event):
        received.append(weakref.ref(event))
        raise RuntimeError('parser-failure')

    monkeypatch.setattr(PopulationCadenceInput, 'from_authority_event', classmethod(fail))
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is None
    assert not pipeline._handled_events and publisher.confirmed_tick == 0
    gc.collect()
    assert received and all(reference() is None for reference in received)
    world.store.close()


def test_changed_cadence_dump_keeps_snapshot_side_effects(tmp_path, monkeypatch):
    from app.population_continuity.siming_contracts import PopulationCadenceInput

    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    original = PopulationCadenceInput.model_dump

    def changed(cadence, *args, **kwargs):
        values = original(cadence, *args, **kwargs)
        values['policy_revision'] = SnapshotWord(values['policy_revision'])
        return values

    monkeypatch.setattr(PopulationCadenceInput, 'model_dump', changed)
    _snapshot_words.clear()
    before_delivery, after_delivery = [], []
    original_route = bus._matches_route

    def observe_route(event, consumer_id):
        if not before_delivery:
            before_delivery.append(len(_snapshot_words))
        return original_route(event, consumer_id)

    monkeypatch.setattr(bus, '_matches_route', observe_route)
    bus.subscribe('population_cadence_event', lambda event: after_delivery.append(len(_snapshot_words)))
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    assert event is not None
    assert after_delivery[0] - before_delivery[0] == 1
    stored = pickle.loads(pipeline._handled_events[event.event_id])
    assert stored.model_dump(mode='json') == event.model_dump(mode='json')
    world.store.close()


def test_changed_snapshot_hook_code_keeps_original_encoding(tmp_path, monkeypatch):
    from app.models.authority_event import AuthorityEvent

    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    function = AuthorityEvent.__getstate__
    original = FunctionType(function.__code__, function.__globals__, function.__name__,
        function.__defaults__, function.__closure__)
    calls = []
    monkeypatch.setitem(function.__globals__, '_snapshot_hook_original', original)
    monkeypatch.setitem(function.__globals__, '_snapshot_hook_calls', calls)
    monkeypatch.setitem(function.__globals__, '_snapshot_hook_event_type', AuthorityEvent)
    monkeypatch.setattr(function, '__code__', changed_snapshot_state.__code__)
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    assert event is not None
    assert len(calls) == 2
    assert pickle.loads(pipeline._handled_events[event.event_id]).model_dump(mode='json') == event.model_dump(mode='json')
    world.store.close()


@pytest.mark.parametrize('failure', [False, True])
def test_copied_context_cannot_keep_borrowed_snapshot_after_callback(tmp_path, failure):
    from app.population_continuity.prepared_frame import population_frame_scope, take_population_ingress_snapshot
    from app.services.authority_event_bus import _prepared_delivery_scope, _prepared_delivery_snapshot

    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / 'gameplay.sqlite3')
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    snapshot = pickle.dumps(event, protocol=pickle.HIGHEST_PROTOCOL)
    receiver = pipeline._handle_prepared_population
    code = SimingEventPipeline._handle_prepared_population.__code__
    expected = pytest.raises(RuntimeError, match='copied-scope') if failure else nullcontext()
    with expected:
        with _prepared_delivery_scope(event, snapshot, receiver):
            with population_frame_scope(event, object(), ingress_snapshot=snapshot):
                copied = copy_context()
                assert copied.run(_prepared_delivery_snapshot, event, receiver, code) is snapshot
                if failure:
                    raise RuntimeError('copied-scope')
    assert copied.run(_prepared_delivery_snapshot, event, receiver, code) is None
    assert copied.run(take_population_ingress_snapshot, event) is None
    world.store.close()
