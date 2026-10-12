from dataclasses import FrozenInstanceError, fields
from enum import Enum
import json
import math

import pytest
from pydantic import BaseModel, model_serializer

from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet, PopulationProjection
from app.population_continuity.publication import publish_authorized_population_cadence
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services import authority_event_bus
from app.models.authority_event import AuthorityEvent
from test_population_durable_cadence_recovery import _publisher, _runtime


def bind(bus, normal, prepared):
    register = getattr(bus, "_subscribe_prepared_population", None)
    assert callable(register), "默认首发需要显式的内部片段交付入口"
    register(normal, prepared)


def test_fresh_delivery_frame_bytes_match_current_event_and_are_immutable(tmp_path):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []

    def normal(event):
        seen.append(event)

    def prepared(event, frame):
        assert frame.projections_json == json.dumps(event.payload["population_projections"],
            sort_keys=True, separators=(",", ":")).encode()
        assert all(type(getattr(frame, field.name)) in (bytes, tuple, str, int) for field in fields(frame))
        with pytest.raises(FrozenInstanceError):
            frame.projections_json = b"[]"
        cadence = PopulationCadenceInput.from_authority_event(event)
        projections = tuple(PopulationProjection.model_validate(row) for row in event.payload["population_projections"])
        actual = frame.read_set(cadence, projections)
        expected = PopulationReadSet.from_inputs(cadence, projections)
        assert actual.read_set_digest == expected.read_set_digest
        assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
        assert all(a is b for a, b in zip(actual.projections, expected.projections, strict=True))
        frames.append(frame)
        normal(event)

    bind(bus, normal, prepared)
    publisher = _publisher(world, bus)
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    assert event is not None and len(seen) == len(frames) == 1
    encoded = frames[0].projections_json
    seen[0].payload["population_projections"][0]["payload"]["state_deltas"]["fatigue"] = 99
    assert frames[0].projections_json == encoded
    assert bus.list_events(include_realtime=True)[0].payload == event.payload


def test_single_parameter_subscribers_keep_independent_original_snapshots(tmp_path):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    values, prepared_values = [], []

    def first(event):
        values.append(event.payload["population_projections"][0]["payload"]["actor_ref"])
        event.payload["population_projections"][0]["payload"]["actor_ref"] = "character:changed"

    def normal(event):
        prepared_values.append(event.payload["population_projections"][0]["payload"]["actor_ref"])

    bus.subscribe("population_cadence_event", first)
    bind(bus, normal, lambda event, frame: normal(event))
    publisher = _publisher(world, bus)
    event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    assert event is not None and values == prepared_values
    assert event.payload["population_projections"][0]["payload"]["actor_ref"] != "character:changed"


def test_later_subscriber_failure_retries_without_the_old_frame(tmp_path):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    frames, normal_events, attempts = [], [], []

    def normal(event):
        normal_events.append(event)

    def prepared(event, frame):
        frames.append(frame)
        normal(event)

    def later(event):
        attempts.append(event.event_id)
        if len(attempts) == 1:
            raise OSError("later_subscriber_failure")

    bind(bus, normal, prepared)
    bus.subscribe("*", later)
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence) is None
    assert publisher.confirmed_tick == 0 and len(frames) == 1
    assert publisher(cadence) is not None
    assert publisher.confirmed_tick == 60 and len(frames) == 1
    assert len(normal_events) == 2 and normal_events[0].model_dump() == normal_events[1].model_dump()
    assert len(bus.list_events(include_realtime=True)) == 1
    assert len(world.store.read_stream(publisher.stream_id)) == 1


def test_publication_preserves_cadence_dump_before_projection_dump(tmp_path, monkeypatch):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    projections = world.build_population_projections(cadence)
    dump = PopulationCadenceInput.model_dump

    def changed(instance, *args, **kwargs):
        projections[0].payload["extension"] = "changed-during-cadence-dump"
        return dump(instance, *args, **kwargs)

    monkeypatch.setattr(PopulationCadenceInput, "model_dump", changed)
    event = publish_authorized_population_cadence(cadence=cadence, store=world.store,
        organization_projection={}, population_projections=projections, event_bus=bus,
        room_id="room", scene_id="scene", zone_id="zone", causation_id="cause", correlation_id="corr")
    assert event is not None
    assert event.payload["population_projections"][0]["payload"].get("extension") == "changed-during-cadence-dump"


def test_modified_dispatcher_transform_uses_original_event_path(tmp_path):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []
    bind(bus, seen.append, lambda event, frame: frames.append(frame))
    publisher = _publisher(world, bus)
    hydrate = publisher.dispatcher._event_transform

    def transform(event):
        event = hydrate(event)
        event.payload["population_projections"][0]["payload"]["actor_ref"] = "character:transformed"
        return event

    publisher.dispatcher._event_transform = transform
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert not frames and seen[0].payload["population_projections"][0]["payload"]["actor_ref"] == "character:transformed"


def test_route_replacing_codec_drops_frame_before_actual_decode(tmp_path, monkeypatch):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []
    bind(bus, seen.append, lambda event, frame: frames.append(frame))
    loads, matches = authority_event_bus.pickle.loads, bus._matches_route

    def changed_loads(value):
        event = loads(value)
        event.payload["population_projections"][0]["payload"]["actor_ref"] = "character:changed-codec"
        return event

    def changed_route(event, consumer_id):
        monkeypatch.setattr(authority_event_bus.pickle, "loads", changed_loads)
        return matches(event, consumer_id)

    monkeypatch.setattr(bus, "_matches_route", changed_route)
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert not frames and seen[0].payload["population_projections"][0]["payload"]["actor_ref"] == "character:changed-codec"


@pytest.mark.parametrize("hook", ["__getstate__", "__setstate__"])
def test_custom_snapshot_hooks_use_actual_snapshot_without_frame(tmp_path, monkeypatch, hook):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []
    bind(bus, seen.append, lambda event, frame: (frames.append(frame), seen.append(event)))
    original = getattr(AuthorityEvent, hook)

    def mutate(event):
        rows = event.payload.get("population_projections")
        if rows:
            rows[0]["payload"]["actor_ref"] = "character:snapshot-hook"

    if hook == "__getstate__":
        def changed(event):
            state = original(event)
            import copy
            state = copy.deepcopy(state)
            rows = state["__dict__"]["payload"].get("population_projections")
            if rows:
                rows[0]["payload"]["actor_ref"] = "character:snapshot-hook"
            return state
    else:
        def changed(event, state):
            original(event, state)
            mutate(event)

    monkeypatch.setattr(AuthorityEvent, hook, changed)
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert not frames
    assert seen[0].payload["population_projections"][0]["payload"]["actor_ref"] == "character:snapshot-hook"


def test_modified_dispatcher_sender_cannot_forward_stale_frame(tmp_path):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []
    bind(bus, seen.append, lambda event, frame: (frames.append(frame), seen.append(event)))
    publisher = _publisher(world, bus)
    sender = publisher.dispatcher._event_publisher

    def changed(event):
        event.payload["population_projections"][0]["payload"]["actor_ref"] = "character:sender"
        return sender(event)

    publisher.dispatcher._event_publisher = changed
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert not frames
    assert seen[0].payload["population_projections"][0]["payload"]["actor_ref"] == "character:sender"


@pytest.mark.parametrize("hook,restore_before_hydrate", [("transform", False), ("transform", True), ("sender", False)])
def test_restoring_delivery_callback_cannot_requalify_changed_event(tmp_path, hook, restore_before_hydrate):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    digests, frames = [], []

    def consume(event, prepared_frame=None):
        cadence = PopulationCadenceInput.from_authority_event(event)
        projections = tuple(PopulationProjection.model_validate(row) for row in event.payload["population_projections"])
        expected = PopulationReadSet.from_inputs(cadence, projections)
        actual = prepared_frame.read_set(cadence, projections) if prepared_frame else expected
        digests.append((actual.read_set_digest, expected.read_set_digest))
        if prepared_frame:
            frames.append(prepared_frame)

    bind(bus, consume, consume)
    publisher = _publisher(world, bus)
    dispatcher = publisher.dispatcher
    hydrate, sender = dispatcher._event_transform, dispatcher._event_publisher

    def transform(event):
        if restore_before_hydrate:
            dispatcher._event_transform = hydrate
        event = hydrate(event)
        event.payload["population_projections"][0]["payload"]["extension"] = "changed-by-transform"
        dispatcher._event_transform = hydrate
        return event

    def publish(event):
        dispatcher._event_publisher = sender
        event.payload["population_projections"][0]["payload"]["extension"] = "changed-by-sender"
        return sender(event)

    if hook == "transform":
        dispatcher._event_transform = transform
    else:
        dispatcher._event_publisher = publish
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert len(digests) == 1 and digests[0][0] == digests[0][1]
    assert not frames
    assert dispatcher._delivery_callbacks is None


class SnapshotString(str):
    def __reduce__(self):
        return str, ("changed-by-pickle",)


class SnapshotWord(str, Enum):
    WORD = "enum"


class SnapshotModel(BaseModel):
    @model_serializer
    def serialize(self):
        return {"word": SnapshotString("serializer"), "bad": math.nan}


@pytest.mark.parametrize("value", [SnapshotString("original"), {"word": SnapshotString("original")},
    [SnapshotString("original"), False, 0], (1, False), SnapshotWord.WORD,
    math.nan, math.inf, SnapshotModel(), "中文"])
def test_native_json_origin_keeps_normalization_and_canonical_bytes(tmp_path, monkeypatch, value):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    build = world.build_population_projections
    seen = []

    def projections(cadence):
        rows = build(cadence)
        rows[0].payload["extension"] = value
        return rows

    def prepared(event, frame):
        cadence = PopulationCadenceInput.from_authority_event(event)
        projections = tuple(PopulationProjection.model_validate(row) for row in event.payload["population_projections"])
        actual = frame.read_set(cadence, projections)
        expected = PopulationReadSet.from_inputs(cadence, projections)
        assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
        assert frame.projections_json == json.dumps(event.payload["population_projections"],
            sort_keys=True, separators=(",", ":")).encode()
        seen.append(actual)

    monkeypatch.setattr(world, "build_population_projections", projections)
    bind(bus, lambda event: pytest.fail("原生 JSON 结果应使用本次首发片段"), prepared)
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    if isinstance(value, BaseModel):
        # 原 world raw 确认不接受任意模型；JSON-mode 来源可验证，但不能扩大其输入合同。
        with pytest.raises(TypeError, match="not JSON serializable"):
            publisher(cadence)
    else:
        assert publisher(cadence) is not None
    assert len(seen) == 1


def test_builder_frame_scope_is_single_use_and_resets_after_failure(tmp_path):
    from app.population_continuity.prepared_frame import population_frame_scope, take_population_frame

    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen = []

    def prepared(event, frame):
        assert take_population_frame(event) is None
        with pytest.raises(OSError, match="scope_failure"):
            with population_frame_scope(event, frame):
                assert take_population_frame(event) is frame
                assert take_population_frame(event) is None
                raise OSError("scope_failure")
        assert take_population_frame(event) is None
        seen.append(event)

    bind(bus, seen.append, prepared)
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert len(seen) == 1


@pytest.mark.parametrize("target", ["dump_function", "adapter_method", "serializer"])
def test_modified_producer_uses_original_single_parameter_delivery(tmp_path, monkeypatch, target):
    from app.population_continuity import publication, siming_contracts

    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []
    adapter = siming_contracts._POPULATION_PROJECTIONS_ADAPTER
    if target == "dump_function":
        dump = publication.dump_population_projections
        def changed(projections):
            rows = dump(projections)
            rows[0]["payload"]["extension"] = "producer-hook"
            return rows
        monkeypatch.setattr(publication, "dump_population_projections", changed)
    elif target == "adapter_method":
        dump = adapter.dump_python
        monkeypatch.setattr(adapter, "dump_python", lambda *args, **kwargs: dump(*args, **kwargs))
    else:
        serializer = adapter.serializer
        class Replacement:
            def to_python(self, *args, **kwargs):
                return serializer.to_python(*args, **kwargs)
        monkeypatch.setattr(adapter, "serializer", Replacement())
    bind(bus, seen.append, lambda event, frame: frames.append(frame))
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert len(seen) == 1 and not frames


@pytest.mark.parametrize("restore_inside", [False, True])
def test_event_constructor_cannot_claim_native_projection_origin(tmp_path, monkeypatch, restore_inside):
    world, bus = _runtime(tmp_path / "gameplay.sqlite3"), InMemoryAuthorityEventBus()
    seen, frames = [], []
    init = AuthorityEvent.__init__

    def changed(instance, **kwargs):
        rows = kwargs["payload"].get("population_projections")
        if rows:
            rows[0]["payload"]["extension"] = SnapshotString("constructor")
        if restore_inside:
            monkeypatch.setattr(AuthorityEvent, "__init__", init)
        return init(instance, **kwargs)

    monkeypatch.setattr(AuthorityEvent, "__init__", changed)
    bind(bus, seen.append, lambda event, frame: (frames.append(frame), seen.append(event)))
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert not frames
    assert seen[0].payload["population_projections"][0]["payload"]["extension"] == "changed-by-pickle"


@pytest.mark.parametrize("consume_frame", [False, True])
@pytest.mark.parametrize("callback_failure", [False, True])
def test_copied_context_cannot_borrow_or_keep_frame_after_scope(consume_frame, callback_failure):
    import gc
    import weakref
    from contextvars import copy_context
    from app.population_continuity.prepared_frame import (
        PreparedPopulationFrame, population_frame_scope, take_population_frame,
    )

    event = AuthorityEvent(event_id="evt:frame-lifetime", event_type="population_cadence_event", producer_ts=1,
        room_id="room:frame-lifetime", scene_id="scene:frame-lifetime", zone_id="zone:frame-lifetime",
        source={"layer": "world", "system": "frame-lifetime-test"},
        routing={"audience_mode": "broadcast", "routing_mode": "same_zone"}, priority="p1", durability="realtime",
        causation_id="cause:frame-lifetime", correlation_id="correlation:frame-lifetime",
        payload={"population_projections": []})
    event_ref = weakref.ref(event)
    frame = PreparedPopulationFrame(b"[]", ())
    failed = False
    try:
        with population_frame_scope(event, frame):
            copied = copy_context()
            if consume_frame:
                assert take_population_frame(event) is frame
            if callback_failure:
                raise RuntimeError("frame-scope-callback-failure")
    except RuntimeError as error:
        assert callback_failure and str(error) == "frame-scope-callback-failure"
        failed = True
    assert failed is callback_failure
    assert copied.run(take_population_frame, event) is None
    # 复制的 context 仍在，也不得延长本次完整帧和事件的生命期。
    del event, frame
    gc.collect()
    assert event_ref() is None
