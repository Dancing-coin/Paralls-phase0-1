import cProfile
from types import MethodType

import pytest

from app.population_continuity import siming_contracts
from app.population_continuity.siming_contracts import PopulationReadSet
from app.population_continuity.prepared_frame import PreparedPopulationFrame
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_population_capability import PopulationSimulationCapability
from app.services import siming_population_capability
from app.models.siming_event import SimingInput
from app.population_continuity.siming_contracts import PopulationCadenceInput
from app.services.siming_runtime import SimingRuntime
from test_population_durable_cadence_recovery import _publisher, _runtime


class RecordingCapability(PopulationSimulationCapability):
    def __init__(self):
        super().__init__()
        self.read_sets = []

    def run_default_decision_cycle(self, cadence, read_set):
        self.read_sets.append(read_set)
        return super().run_default_decision_cycle(cadence, read_set)


def case(path):
    world, bus = _runtime(path), InMemoryAuthorityEventBus()
    capability = RecordingCapability()
    runtime = SimingRuntime(population_capability=capability)
    writer = SimingAuditWriter()
    pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(), runtime=runtime,
        producer=SimingEventProducer(bus), audit_writer=writer)
    prepared = getattr(pipeline, "_handle_prepared_population", None)
    assert callable(prepared), "Siming 需要绑定实际事件副本的内部片段入口"
    bus._subscribe_prepared_population(pipeline.handle_event, prepared)
    return world, bus, capability, runtime, pipeline, _publisher(world, bus)


def test_default_pipeline_reuses_producer_bytes_and_keeps_native_read_set(tmp_path):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / "gameplay.sqlite3")
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    finally:
        profiler.disable()
    assert event is not None and len(capability.read_sets) == 1
    actual = capability.read_sets[0]
    expected = PopulationReadSet.from_inputs(actual.cadence, actual.projections)
    assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
    dump_code = siming_contracts.dump_population_projections.__code__
    # 发布及 capability 的筛选后决策读集编码保留，省去 builder 的全人口重复编码。
    assert sum(item.callcount for item in profiler.getstats() if item.code is dump_code) == 2
    frame_code = PreparedPopulationFrame.read_set.__code__
    assert sum(item.callcount for item in profiler.getstats() if item.code is frame_code) == 1
    assert event.event_id in pipeline._handled_events
    assert bus.list_events(include_realtime=True)[0].payload == event.payload


@pytest.mark.parametrize("target", ["consumer", "tick", "new_frame", "outcome", "builder"])
def test_mutating_input_hooks_keep_original_builder_results(tmp_path, monkeypatch, target):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / "gameplay.sqlite3")

    def mutate(event):
        event.payload["population_projections"][0]["payload"]["extension"] = "中文"

    if target == "consumer":
        consume = pipeline._consumer.handle_event
        def changed(instance, event):
            mutate(event)
            return consume(event)
        monkeypatch.setattr(pipeline._consumer, "handle_event", MethodType(changed, pipeline._consumer))
    elif target == "tick":
        tick = runtime.tick
        def changed(instance, inputs):
            mutate(inputs[0].source_event)
            return tick(inputs)
        monkeypatch.setattr(runtime, "tick", MethodType(changed, runtime))
    elif target == "new_frame":
        new_frame = runtime._new_frame
        def changed(instance, siming_input, **kwargs):
            mutate(siming_input.source_event)
            return new_frame(siming_input, **kwargs)
        monkeypatch.setattr(runtime, "_new_frame", MethodType(changed, runtime))
    elif target == "outcome":
        outcome = runtime.record_authority_outcome
        def changed(instance, event):
            mutate(event)
            return outcome(event)
        monkeypatch.setattr(runtime, "record_authority_outcome", MethodType(changed, runtime))
    else:
        builder = runtime._population_read_set_builder
        def changed(event, cadence):
            mutate(event)
            return builder(event, cadence)
        runtime._population_read_set_builder = changed
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert len(capability.read_sets) == 1
    actual = capability.read_sets[0]
    assert actual.projections[0].payload["extension"] == "中文"
    assert actual.read_set_digest == PopulationReadSet.from_inputs(actual.cadence, actual.projections).read_set_digest


@pytest.mark.parametrize("target", ["cadence_parser", "projection_validator", "restoring_validator", "input_constructor"])
def test_ingress_extensions_cannot_reuse_unchanged_producer_bytes(tmp_path, monkeypatch, target):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / "gameplay.sqlite3")
    if target == "cadence_parser":
        parser = PopulationCadenceInput.from_authority_event
        def changed(cls, event):
            event.payload["population_projections"][0]["payload"]["extension"] = "ingress"
            return parser(event)
        monkeypatch.setattr(PopulationCadenceInput, "from_authority_event", classmethod(changed))
    elif target in {"projection_validator", "restoring_validator"}:
        adapter = siming_population_capability._POPULATION_PROJECTIONS_ADAPTER
        validate = adapter.validate_python
        def changed(value, **kwargs):
            projections = validate(value, **kwargs)
            projections[0].payload["extension"] = "ingress"
            if target == "restoring_validator":
                monkeypatch.setattr(adapter, "validate_python", validate)
            return projections
        monkeypatch.setattr(adapter, "validate_python", changed)
    else:
        init = SimingInput.__init__
        def changed(instance, **kwargs):
            kwargs["source_event"].payload["population_projections"][0]["payload"]["extension"] = "ingress"
            return init(instance, **kwargs)
        monkeypatch.setattr(SimingInput, "__init__", changed)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    actual = capability.read_sets[0]
    assert actual.projections[0].payload["extension"] == "ingress"
    assert actual.read_set_digest == PopulationReadSet.from_inputs(actual.cadence, actual.projections).read_set_digest


@pytest.mark.parametrize("event_type", ["population_cadence_event", "*"])
def test_public_mutating_forwarder_keeps_original_path(tmp_path, event_type):
    world, bus, capability, runtime, pipeline, publisher = case(tmp_path / "gameplay.sqlite3")
    bus._subscribers["population_cadence_event"].clear()

    def forward(event):
        event.payload["population_projections"][0]["payload"]["extension"] = "forwarder"
        return pipeline.handle_event(event)

    bus.subscribe(event_type, forward)
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        event = publisher(world.build_population_cadence(window_start=0, window_end=60))
    finally:
        profiler.disable()
    assert event is not None
    actual = capability.read_sets[0]
    assert actual.projections[0].payload["extension"] == "forwarder"
    assert actual.read_set_digest == PopulationReadSet.from_inputs(actual.cadence, actual.projections).read_set_digest
    assert not any(item.code is PreparedPopulationFrame.read_set.__code__ for item in profiler.getstats())


@pytest.mark.parametrize("custom_handler", [False, True])
def test_main_composition_uses_frame_only_for_its_original_receiver(monkeypatch, custom_handler):
    from app import main

    main.stop_population_runtime()
    handler = main._handle_siming_authority_event
    if custom_handler:
        def changed(event):
            if event.event_type == "population_cadence_event":
                event.payload["population_projections"][0]["payload"]["extension"] = "handler"
            return handler(event)
        monkeypatch.setattr(main, "_handle_siming_authority_event", changed)
    main.reset_runtime_state()
    try:
        driver = main._build_population_driver()
        assert driver is not None
        profiler = cProfile.Profile()
        profiler.enable()
        try:
            result = driver.tick(driver.current_tick + driver.window_size)
        finally:
            profiler.disable()
        assert not result.rejected_windows
        frame_code = PreparedPopulationFrame.read_set.__code__
        count = sum(item.callcount for item in profiler.getstats() if item.code is frame_code)
        assert count == (0 if custom_handler else 1)
    finally:
        main.stop_population_runtime()
        monkeypatch.setattr(main, "_handle_siming_authority_event", handler)
        main.reset_runtime_state()
