"""公共确认和内部 B1 共用 admission，原始域输入跨失败/重开保持不变。"""
from __future__ import annotations

import pytest

from app.gameplay.dispatcher import GameplayOutboxDispatcher
from app.gameplay.organization_government_runtime import OrganizationAuthority, OperatingWindowDueRequest
from app.population_continuity.owner_adapters import OrganizationOperatingWindowDueOwnerExecutor
from app.population_continuity.recovery import durable_population_receipt
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_population_capability import PopulationSimulationCapability
from test_population_durable_cadence_recovery import _publisher, _runtime
from test_population_organization_due_source import schedule, window


DOMAIN_TOPIC = "population_domain_cadence_event"


def setup(path, count=1):
    world = _runtime(path, tuple(f"worker_{i}" for i in range(count)))
    authority = OrganizationAuthority(store=world.store)
    for i, actor in enumerate(world.roster.actor_ids):
        schedule(authority, str(i), actor, organization=f"org:{i % 2}")
        window(authority, str(i), organization=f"org:{i % 2}")
    return world


def is_domain(event):
    return event.payload["population_cadence"]["report_scope"] == "organization:summary"


def consumer(world, bus, seen, *, fail=False):
    capability = PopulationSimulationCapability(owner_executors={
        "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
            authority=OrganizationAuthority(store=world.store))})

    def consume(event):
        seen.append(event)
        if not is_domain(event):
            return
        parent = PopulationCadenceInput.model_validate(event.payload["public_population_cadence"])
        assert durable_population_receipt(world, parent) is not None
        if fail:
            raise RuntimeError("domain_consumer_unavailable")
        cadence = PopulationCadenceInput.from_authority_event(event)
        projections = event.payload["population_projections"]
        from app.population_continuity.siming_contracts import PopulationProjection
        result = capability.run_default_decision_cycle(cadence, PopulationReadSet.from_inputs(
            cadence, tuple(PopulationProjection.model_validate(value) for value in projections)))
        assert result.status == "accepted", result.reason

    bus.subscribe("population_cadence_event", consume)


def settled(world):
    return [row for row in world.store.read_events() if row.event_type == "gameplay.organization.operating_window_due_recorded"]


def real_pipeline(world, bus, *, authority=None, missing_adapter=False):
    from app.services.siming_audit_writer import SimingAuditWriter
    from app.services.siming_event_consumer import SimingEventConsumer
    from app.services.siming_event_pipeline import SimingEventPipeline
    from app.services.siming_event_producer import SimingEventProducer
    from app.services.siming_runtime import SimingRuntime

    capability = PopulationSimulationCapability(owner_executors={} if missing_adapter else {
        "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(
            authority=authority or OrganizationAuthority(store=world.store))})
    pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(),
        runtime=SimingRuntime(population_capability=capability), producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter())
    bus.subscribe("population_cadence_event", pipeline.handle_event)
    return capability, pipeline


def test_public_and_domain_share_admission_but_only_domain_selects_32_real_actors(tmp_path):
    world = setup(tmp_path / "gameplay.sqlite3", 40)
    bus, seen = InMemoryAuthorityEventBus(), []
    consumer(world, bus, seen)
    publisher = _publisher(world, bus)
    first = world.build_population_cadence(window_start=0, window_end=60, budget=100)
    public = publisher(first)
    assert public is not None and not is_domain(public)
    assert all(row["payload"]["fidelity_tier"] == "B0" for row in public.payload["population_projections"])
    assert len(seen) == 2 and len(settled(world)) == 32
    admission = world.store.read_stream(publisher.stream_id)[0]
    entries = world.store.get_transaction(admission.transaction_id).outbox_entries
    assert {entry.topic for entry in entries} == {"population_cadence_event", DOMAIN_TOPIC}
    assert {entry.event_id for entry in entries} == {admission.event_id}
    assert first.catch_up_limit < 32
    assert publisher.confirmed_tick == 60
    second = world.build_population_cadence(window_start=60, window_end=120, budget=100)
    assert publisher(second) is not None
    assert len(settled(world)) == 40
    assert len([row for row in seen if is_domain(row)]) == 2
    assert publisher.confirmed_tick == 120
    assert all(world.population_hot_state.read(actor)["last_update_tick"] == 120 for actor in world.roster.actor_ids)
    assert not world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)


def test_no_domain_admission_without_real_due_work(tmp_path):
    world = _runtime(tmp_path / "gameplay.sqlite3")
    bus = InMemoryAuthorityEventBus()
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert len(world.store.list_outbox()) == 1
    assert not world.store.list_outbox(topic=DOMAIN_TOPIC)


def test_unconfirmed_public_blocks_domain_even_for_generic_dispatcher(tmp_path):
    world = setup(tmp_path / "gameplay.sqlite3")
    bus, seen = InMemoryAuthorityEventBus(), []

    def fail_public(event):
        seen.append(event)
        raise RuntimeError("public_consumer_unavailable")

    bus.subscribe("population_cadence_event", fail_public)
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence) is None
    pending = world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert len(pending) == 1 and pending[0].attempt_count == 0
    assert durable_population_receipt(world, cadence) is None
    assert not any(is_domain(event) for event in seen)
    assert GameplayOutboxDispatcher(store=world.store, bus=bus).dispatch_pending(topic=DOMAIN_TOPIC).published_count == 0
    assert not settled(world)


@pytest.mark.parametrize("cut", ["before_confirmation", "domain_delivery"])
def test_reopen_keeps_frozen_domain_and_does_not_republish_public(tmp_path, monkeypatch, cut):
    path = tmp_path / "gameplay.sqlite3"
    world = setup(path)
    bus, seen = InMemoryAuthorityEventBus(), []
    consumer(world, bus, seen, fail=True)
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    if cut == "before_confirmation":
        monkeypatch.setattr(publisher, "_confirm", lambda *_: (_ for _ in ()).throw(RuntimeError("confirmation_crash")))
        with pytest.raises(RuntimeError, match="confirmation_crash"):
            publisher(cadence)
    else:
        assert publisher(cadence) is not None
    pending = world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert len(pending) == 1
    record = world.store.get_event(pending[0].event_id).payload
    frozen = record["domain_authority_event"]
    # 新来源不能重写旧 admission 的 pins、请求相关身份或窗口。
    schedule(OrganizationAuthority(store=world.store), "later", "worker_0", window="window:later")
    reopened = _runtime(path, ("worker_0",))
    reopened_bus, restored_seen = InMemoryAuthorityEventBus(), []
    consumer(reopened, reopened_bus, restored_seen)
    restored = _publisher(reopened, reopened_bus)
    assert restored.confirmed_tick == 60
    assert restored._dispatch_domains()
    assert restored(cadence) is not None
    assert len(restored_seen) == 1 and is_domain(restored_seen[0])
    assert restored_seen[0].model_dump(mode="json") == frozen
    assert len(settled(reopened)) == 1
    assert restored(cadence) is not None
    assert len(restored_seen) == 1


def test_failed_domain_does_not_stop_b0_or_create_overlapping_domain_admissions(tmp_path):
    world = setup(tmp_path / "gameplay.sqlite3")
    bus, seen = InMemoryAuthorityEventBus(), []
    consumer(world, bus, seen, fail=True)
    publisher = _publisher(world, bus)
    for ordinal in range(3):
        assert publisher(world.build_population_cadence(window_start=ordinal * 60, window_end=(ordinal + 1) * 60)) is not None
    assert publisher.confirmed_tick == 180
    assert len(world.store.list_outbox(topic=DOMAIN_TOPIC)) == 1
    assert not settled(world)


def test_domain_source_fence_rejects_changed_owner_fact_before_atomic_admission(tmp_path, monkeypatch):
    world = setup(tmp_path / "gameplay.sqlite3")
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    append = world.store.append_batch

    def race(batch):
        if batch.events[0].event_type == "population.cadence.admitted":
            schedule(OrganizationAuthority(store=world.store), "racing", "worker_0", organization="org:0", window="window:racing")
        return append(batch)

    monkeypatch.setattr(world.store, "append_batch", race)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is None
    assert not world.store.read_stream(publisher.stream_id)
    assert not world.store.list_outbox(topic=DOMAIN_TOPIC)


def test_no_consumer_is_not_a_domain_completion_and_due_work_survives(tmp_path):
    world = setup(tmp_path / "gameplay.sqlite3")
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    assert not settled(world)
    pending = world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert len(pending) == 1 and pending[0].attempt_count == 1
    assert any(obligation.startswith("projection:organization-window-due:") for _, obligation, _ in world.select_due_population_work(60))


def test_real_siming_requeues_without_dedup_poison_then_retries_original_input(tmp_path):
    world = setup(tmp_path / "gameplay.sqlite3")
    bus = InMemoryAuthorityEventBus()
    capability, pipeline = real_pipeline(world, bus, missing_adapter=True)
    publisher = _publisher(world, bus)
    assert publisher(world.build_population_cadence(window_start=0, window_end=60)) is not None
    pending = world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert len(pending) == 1
    original = world.store.get_event(pending[0].event_id).payload["domain_authority_event"]
    assert original["event_id"] not in pipeline._handled_events
    capability._owner_executors["population:organization-window-due:v1"] = OrganizationOperatingWindowDueOwnerExecutor(
        authority=OrganizationAuthority(store=world.store))
    assert publisher(world.build_population_cadence(window_start=60, window_end=120)) is not None
    assert len(settled(world)) == 1
    assert not world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert len(world.store.list_outbox(topic=DOMAIN_TOPIC)) == 1
    assert settled(world)[0].payload["owner_intent_digest"] == OrganizationAuthority._operating_window_due_intent_digest(
        OperatingWindowDueRequest.model_validate(
            next(iter(original["payload"]["population_owner_requests"].values()))))


def test_committed_prefix_reopens_with_original_requests_and_one_remaining_batch(tmp_path, monkeypatch):
    path = tmp_path / "gameplay.sqlite3"
    world = setup(path, 3)
    bus = InMemoryAuthorityEventBus()
    authority = OrganizationAuthority(store=world.store)
    batch_submit = authority.record_operating_windows_due_batch

    def cut_after_first(requests):
        prefix = batch_submit(requests[:1])
        assert prefix.results[requests[0].command_id].committed
        raise RuntimeError("owner_prefix_cut")

    monkeypatch.setattr(authority, "record_operating_windows_due_batch", cut_after_first)
    real_pipeline(world, bus, authority=authority)
    publisher = _publisher(world, bus)
    cadence = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(cadence) is not None
    prefix = settled(world)
    assert len(prefix) == 1
    pending = world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert len(pending) == 1
    original = world.store.get_event(pending[0].event_id).payload["domain_authority_event"]
    reopened = _runtime(path, world.roster.actor_ids)
    restored_bus = InMemoryAuthorityEventBus()
    real_pipeline(reopened, restored_bus)
    restored = _publisher(reopened, restored_bus)
    appends = []
    append = reopened.store.append_batch

    def count(batch):
        appends.append(batch)
        return append(batch)

    monkeypatch.setattr(reopened.store, "append_batch", count)
    assert restored._dispatch_domains()
    assert restored(cadence) is not None
    assert len(settled(reopened)) == 3
    assert reopened.store.get_event(prefix[0].event_id) == prefix[0]
    assert len(appends) == 1 and len(appends[0].events) == 2
    assert not reopened.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    assert restored_bus.list_events(event_type="population_cadence_event", include_realtime=True)[0].model_dump(mode="json") == original
    assert not any(obligation.startswith("projection:organization-window-due:") for _, obligation, _ in reopened.select_due_population_work(60))


def test_full_checkpoint_reconciles_domain_committed_after_public_snapshot(tmp_path):
    path = tmp_path / "gameplay.sqlite3"
    world = _runtime(path, ("worker_0",))
    authority = OrganizationAuthority(store=world.store)
    schedule(authority, "late", "worker_0")
    window(authority, "late", due=960)
    bus = InMemoryAuthorityEventBus()
    real_pipeline(world, bus)
    publisher = _publisher(world, bus)
    for i in range(16):
        assert publisher(world.build_population_cadence(window_start=i * 60, window_end=(i + 1) * 60)) is not None
    assert len(settled(world)) == 1
    reopened = _runtime(path, ("worker_0",))
    restored = _publisher(reopened, InMemoryAuthorityEventBus())
    assert restored.confirmed_tick == 960 and restored.replayed_windows == 0
    assert not any(obligation.startswith("projection:organization-window-due:") for _, obligation, _ in reopened.select_due_population_work(960))


def test_main_driver_consumes_real_organization_work_on_its_existing_store():
    from app import main

    main.stop_population_runtime()
    main.reset_runtime_state()
    try:
        authority = OrganizationAuthority(store=main.gameplay_event_store)
        actors = main.population_roster.actor_ids[:6]
        for i, actor in enumerate(actors):
            schedule(authority, f"main-{i}", actor)
            window(authority, f"main-{i}")
        driver = main._build_population_driver()
        assert driver is not None
        first = driver.tick(driver.current_tick + driver.window_size)
        assert not first.rejected_windows and first.b0_advanced_count == len(main.population_roster.actor_ids)
        committed = [row for row in main.gameplay_event_store.read_events() if row.event_type == "gameplay.organization.operating_window_due_recorded"]
        assert len(committed) == min(driver.world_runtime.mode.batch_limit, len(actors))
        second = driver.tick(driver.current_tick + driver.window_size)
        assert not second.rejected_windows
        committed = [row for row in main.gameplay_event_store.read_events() if row.event_type == "gameplay.organization.operating_window_due_recorded"]
        assert len(committed) == len(actors)
        assert not main.gameplay_event_store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)
    finally:
        main.stop_population_runtime()
        main.reset_runtime_state()

@pytest.mark.parametrize('windows', [2, 17])
@pytest.mark.parametrize('completed', [False, True])
def test_old_domain_completion_reconciles_after_newer_public_snapshot(tmp_path, monkeypatch, windows, completed):
    path = tmp_path / 'delayed-domain.sqlite3'
    world = setup(path)
    bus = InMemoryAuthorityEventBus()
    capability, _ = real_pipeline(world, bus, missing_adapter=True)
    publisher = _publisher(world, bus)
    for index in range(windows):
        assert publisher(world.build_population_cadence(window_start=index * 60, window_end=(index + 1) * 60)) is not None
    pending = world.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)[0]
    original = world.store.get_event(pending.event_id).payload['domain_authority_event']
    def domain_due(runtime):
        return tuple(row for row in runtime._population_due_index.export_entries()
                     if row[1].startswith('projection:organization-window-due:'))
    due_before = domain_due(world)
    if completed:
        capability._owner_executors['population:organization-window-due:v1'] = OrganizationOperatingWindowDueOwnerExecutor(
            authority=OrganizationAuthority(store=world.store))
        append = world.store.append_batch
        def crash_new_public(batch):
            if batch.events[0].event_type == 'population.cadence.admitted':
                raise RuntimeError('after_old_domain_before_new_public')
            return append(batch)
        monkeypatch.setattr(world.store, 'append_batch', crash_new_public)
        with pytest.raises(RuntimeError, match='after_old_domain_before_new_public'):
            publisher(world.build_population_cadence(window_start=windows * 60, window_end=(windows + 1) * 60))
        assert len(settled(world)) == 1
        assert not domain_due(world)
    reopened = _runtime(path, ('worker_0',))
    restored_bus = InMemoryAuthorityEventBus()
    def no_history(*args, **kwargs):
        raise AssertionError('restore must not scan complete history')
    with monkeypatch.context() as patch:
        patch.setattr(reopened.store, 'read_events', no_history)
        restored = _publisher(reopened, restored_bus)
    assert restored.confirmed_tick == windows * 60
    assert len(settled(reopened)) == int(completed)
    assert domain_due(reopened) == (() if completed else due_before)
    assert reopened.store.get_event(pending.event_id).payload['domain_authority_event'] == original
    assert len(reopened.store.list_outbox(include_delivered=False, topic=DOMAIN_TOPIC)) == int(not completed)
    assert restored_bus.list_events(event_type='population_cadence_event', include_realtime=True) == []

def test_confirmed_public_replay_never_pumps_pending_domain(tmp_path):
    world = setup(tmp_path / 'replay-domain.sqlite3')
    bus = InMemoryAuthorityEventBus()
    capability, _ = real_pipeline(world, bus, missing_adapter=True)
    publisher = _publisher(world, bus)
    first = world.build_population_cadence(window_start=0, window_end=60)
    assert publisher(first) is not None
    assert publisher(world.build_population_cadence(window_start=60, window_end=120)) is not None
    capability._owner_executors['population:organization-window-due:v1'] = OrganizationOperatingWindowDueOwnerExecutor(
        authority=OrganizationAuthority(store=world.store))
    before_store = world.store.export_snapshot()
    before_world = world.export_recovery_state()
    before_bus = bus.list_events(include_realtime=True)
    assert publisher(first) is not None
    assert world.store.export_snapshot() == before_store
    assert world.export_recovery_state() == before_world
    assert bus.list_events(include_realtime=True) == before_bus
    with pytest.raises(ValueError, match='confirmation_conflict'):
        publisher(first.model_copy(update={'window_end': 61}))
    assert world.store.export_snapshot() == before_store
    assert not settled(world)
