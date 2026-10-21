"""Application assembly proof: no direct expiration selection/dispatch in these tests."""
import asyncio
from dataclasses import replace

import pytest
import pytest_asyncio

from app.gameplay.status_tags import StatusTagCommand
from test_phase3_mirror_source import _configuration


def _config(*, binding=True):
    value = _configuration("actor:configured").model_dump(mode="json")
    value["status_tag_definitions"] = [dict(tag_id=tag, definition_version="1") for tag in ("timed", "other", "third", "permanent")]
    if binding:
        value["status_time_binding"] = dict(
            world_ref="world:bakery-district", timeline_id="population:world:bakery-district",
            profile_revision="population-seconds:v1", mapping_id="population-seconds:world:bakery-district",
            mapping_revision="population-seconds:v1", source_clock_ref="population-driver:world:bakery-district",
            source_unit_ref="second", source_revision="population-seconds:v1", canonical_unit_ref="second",
            step_duration="1/1", window_ticks=86400,
        )
    return value


def _command(key, tag="timed", operation="apply", instance_id=None):
    return StatusTagCommand(command_id=key, actor_ref="actor:configured", authority_principal="gameplay_authority",
        idempotency_key=key, payload_digest=key, causation_id=key, correlation_id=key,
        operation=operation, tag_id=tag, source_ref="test:configured", instance_id=instance_id)


@pytest_asyncio.fixture
async def application(tmp_path, monkeypatch):
    from app import main
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "world.sqlite3"))
    monkeypatch.setattr(main.settings, "gameplay_mirror_phase3_actor_configs", [_config()])
    target = [0]
    wake = asyncio.Queue()
    idle = asyncio.Queue()

    async def sleep(_):
        await idle.put(True)
        await wake.get()

    monkeypatch.setattr(main, "_population_runtime_sleep", sleep)
    monkeypatch.setattr(main, "_population_runtime_clock", lambda *_: target[0])

    async def start():
        await main._start_population_runtime_on_startup()
        await asyncio.wait_for(idle.get(), 5)

    async def advance(tick):
        target[0] = tick
        await wake.put(True)
        await asyncio.wait_for(idle.get(), 5)
        assert main.get_population_runtime_failure() is None

    try:
        yield main, start, advance
    finally:
        await main._stop_population_runtime_on_shutdown()


async def _apply(main, key, tag="timed", duration=None, **kw):
    return await asyncio.wrap_future(main.submit_status_tag_command(_command(key, tag, **kw), expires_after_steps=duration))


async def _events(main):
    return await asyncio.wrap_future(main.runtime_execution.submit(
        lambda: [e for e in main.gameplay_event_store.read_events() if e.event_type.startswith("gameplay.status_tag.")]))


@pytest.mark.asyncio
async def test_application_caller_durable_shutdown_restart_receipts_and_duplicate_dispatch(application, record_property):
    from app.gameplay.event_store import DurableGameplayEventStore
    main, start, advance = application
    await start()
    assert isinstance(main.gameplay_event_store, DurableGameplayEventStore)
    first_store, first_service, first_caller = main.gameplay_event_store, main.status_tag_service, main.status_temporal_consumer
    applied = await _apply(main, "timed", duration=172800)
    assert applied.accepted and applied.append_result.committed
    await advance(86400)
    assert len(await _events(main)) == 1
    await main._stop_population_runtime_on_shutdown()
    assert main.status_tag_service is None and main.status_temporal_consumer is None
    await start()
    assert main.gameplay_event_store is not first_store and main.status_tag_service is not first_service
    assert main.status_temporal_consumer is not first_caller
    assert main._population_runtime_driver.current_tick == 86400
    work = main.status_temporal_consumer.pending_work()[0]
    await advance(172800)
    events = await _events(main)
    assert [e.event_type for e in events] == ["gameplay.status_tag.applied", "gameplay.status_tag.expired"]
    receipt = main.status_temporal_consumer.last_results[0].append_result
    assert receipt.committed and receipt.committed_event_ids == [events[-1].event_id]
    await main._stop_population_runtime_on_shutdown()
    await start()
    await advance(259200)
    assert len(await _events(main)) == 2
    duplicate = await asyncio.wrap_future(main.runtime_execution.submit(lambda:
        main.status_tag_service.submit_expiration_request(work,
            temporal=main.status_temporal_consumer.context(main._population_runtime_driver, "actor:configured"))))
    assert duplicate.append_result == receipt
    assert len(await _events(main)) == 2
    record_property("status_restart_evidence", str(dict(
        caller="PopulationCadenceDriver.run_forever -> tick -> StatusTemporalConsumer.advance",
        store="DurableGameplayEventStore", normal_shutdowns=2, new_store_service_instances=True,
        applied_receipt=applied.append_result.model_dump(mode="json"),
        expired_receipt=receipt.model_dump(mode="json"), exact_restarted_duplicate=True)))
    assert main.status_temporal_consumer.pending_work() == ()
    # Startup is idempotent, without a duplicate driver/caller.
    driver, consumer = main._population_runtime_driver, main.status_temporal_consumer
    await main._start_population_runtime_on_startup()
    assert main._population_runtime_driver is driver and main.status_temporal_consumer is consumer


@pytest.mark.asyncio
async def test_multiple_deadlines_budget_pause_failure_and_removed_state_survive(application, monkeypatch):
    main, start, advance = application
    await start()
    await _apply(main, "forever", "permanent")
    assert main.status_temporal_consumer.pending_work() == ()
    for key, tag in (("a", "timed"), ("b", "other"), ("c", "third")):
        await _apply(main, key, tag, duration=86400)
    await _apply(main, "remove", "third", operation="remove", instance_id="tag:c")
    owner = main.runtime_execution
    driver = main._population_runtime_driver
    # Failure occurs after a real confirmed time boundary; active events remain the durable queue.
    original = main.status_tag_service.submit_expiration_request
    monkeypatch.setattr(main.status_tag_service, "submit_expiration_request", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected")))
    await advance(86400)
    assert len(main.status_temporal_consumer.pending_work()) == 2
    assert main.status_temporal_consumer.last_errors
    monkeypatch.setattr(main.status_tag_service, "submit_expiration_request", original)
    await asyncio.wrap_future(owner.submit(lambda: driver.world_runtime.pause(reason="test")))
    await advance(172800)
    assert len(main.status_temporal_consumer.pending_work()) == 2
    await asyncio.wrap_future(owner.submit(lambda: driver.world_runtime.resume()))
    driver.catch_up_limit = 0
    await advance(172800)
    assert len(main.status_temporal_consumer.pending_work()) == 2
    driver.catch_up_limit = 1
    await advance(86400)  # same confirmed boundary retries pending work with finite budget
    assert len(main.status_temporal_consumer.pending_work()) == 1
    await main._stop_population_runtime_on_shutdown()
    await start()
    await advance(172800)
    events = await _events(main)
    assert len([e for e in events if e.event_type.endswith("expired")]) == 2
    assert all(e.payload["instance_id"] != "tag:c" for e in events if e.event_type.endswith("expired"))
    active = main.status_tag_service.projector.rebuild("actor:configured", events).active_instances
    assert list(active) == ["tag:forever"]


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("mapping_revision", "stale"), ("source_unit_ref", "frame"), ("profile_revision", "stale"), ("window_ticks", 1)])
async def test_unadmitted_binding_rejects_startup(application, field, value):
    main, start, _ = application
    main.settings.gameplay_mirror_phase3_actor_configs[0]["status_time_binding"][field] = value
    with pytest.raises(ValueError, match="status_time_binding_mismatch"):
        await start()
    assert main.runtime_execution is None


@pytest.mark.asyncio
async def test_missing_mapping_denies_timed_apply_but_permanent_is_compatible(application):
    main, start, _ = application
    main.settings.gameplay_mirror_phase3_actor_configs = [_config(binding=False)]
    await start()
    assert (await _apply(main, "permanent", "permanent")).accepted
    with pytest.raises(ValueError, match="status_time_binding_missing"):
        await _apply(main, "timed", duration=1)


@pytest.mark.asyncio
async def test_missing_confirmed_temporal_pins_zero_write_in_strict_mode(application):
    main, start, advance = application
    await start()
    await _apply(main, "timed", duration=86400)
    publish = main._population_runtime_driver.publish_window
    publish.confirmed_time_pins = lambda: None
    await advance(86400)
    assert [e for e in await _events(main) if e.event_type.endswith("expired")] == []
    assert any("status_temporal_authorization_rejected" in error for _, error in main.status_temporal_consumer.last_errors)


def test_reset_replaces_service_and_closes_old_consumer(monkeypatch):
    from app import main
    monkeypatch.setattr(main.settings, "gameplay_mirror_phase3_actor_configs", [_config()])
    main.reset_runtime_state()
    previous, store = main.status_temporal_consumer, main.gameplay_event_store
    main.reset_runtime_state()
    try:
        assert main.status_temporal_consumer is not previous
        assert main.gameplay_event_store is not store
        with pytest.raises(RuntimeError, match="status_consumer_closed"):
            previous.pending_work()
    finally:
        main.close_runtime_resources()



@pytest.mark.asyncio
async def test_same_actor_three_simultaneous_deadlines_revalidate_after_each_commit(application):
    main, start, advance = application
    await start()
    for key, tag in (("a", "timed"), ("b", "other"), ("c", "third")):
        await _apply(main, key, tag, duration=86400)
    await advance(86400)
    assert len(main.status_temporal_consumer.last_results) == 2
    assert all(item.accepted and item.append_result.committed for item in main.status_temporal_consumer.last_results)
    assert len(main.status_temporal_consumer.pending_work()) == 1
    await advance(86400)
    assert main.status_temporal_consumer.pending_work() == ()
    assert len([e for e in await _events(main) if e.event_type.endswith("expired")]) == 3


@pytest.mark.asyncio
async def test_missing_mapping_on_restart_preserves_committed_status_and_denies_startup(application):
    main, start, advance = application
    await start()
    await _apply(main, "a", duration=86400)
    await main._stop_population_runtime_on_shutdown()
    main.settings.gameplay_mirror_phase3_actor_configs = [_config(binding=False)]
    with pytest.raises(ValueError, match="status_time_binding_missing"):
        await start()
    assert main.runtime_execution is None
    main.settings.gameplay_mirror_phase3_actor_configs = [_config()]
    await start()
    await advance(86400)
    assert len([e for e in await _events(main) if e.event_type.endswith("expired")]) == 1


@pytest.mark.asyncio
async def test_runtime_mapping_change_keeps_work_and_shutdown_denies_new_ingress(application):
    main, start, advance = application
    await start()
    await _apply(main, "a", duration=86400)
    driver = main._population_runtime_driver
    driver.mapping = replace(driver.mapping, revision="changed")
    # No new time is admitted; validation also runs on the already confirmed boundary.
    await advance(0)
    assert main.status_temporal_consumer.last_errors
    assert len(main.status_temporal_consumer.pending_work()) == 1
    main._mirror_transport_accepting = False
    with pytest.raises(RuntimeError, match="runtime_stopped"):
        main.submit_status_tag_command(_command("after-shutdown"))
