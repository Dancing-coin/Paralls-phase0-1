"""Actual application owner activation; cadence remains canonical seconds."""
import asyncio
from dataclasses import replace
from fractions import Fraction
import json

import pytest

from test_status_application_lifecycle import application, _apply, _events


def request(main, key="migration:1", duration=Fraction(2, 3)):
    driver = main._population_runtime_driver
    return dict(migration_id=key, advancement_owner_ref=driver.clock.timeline.advancement_owner_ref,
        boundary="window", expected_timeline_revision=driver.clock.timeline.authoritative_revision,
        expected_owner_revisions={f"gameplay:status_tags:{actor}": main.gameplay_event_store.get_stream_head(f"gameplay:status_tags:{actor}")
            for actor in main.status_temporal_consumer.bindings},
        profile=replace(driver.clock.temporal_profile, revision="population-thirds:v2", step_duration=duration, rounding_policy="ceil"),
        mapping=replace(driver.mapping, revision="population-thirds:v2", target_profile_revision="population-thirds:v2", ratio=1 / duration))


@pytest.mark.asyncio
async def test_actual_activation_remaining_rounding_receipts_and_durable_restart(application, record_property):
    main, start, advance = application
    await start()
    await _apply(main, "timed", duration=86401)
    await advance(86400)
    old_work = main.status_temporal_consumer.pending_work()[0]
    args = request(main)
    receipt = await asyncio.wrap_future(main.submit_temporal_profile_migration(**args))
    assert receipt.committed
    driver = main._population_runtime_driver
    assert driver.current_tick == 86400
    assert driver.clock.tick == 129600
    assert driver.clock.tick * driver.clock.temporal_profile.step_duration == 86400
    work = main.status_temporal_consumer.pending_work()[0]
    assert work.work_ref == old_work.work_ref and work.trigger_ref == old_work.trigger_ref
    assert work.due_time.step_index == 129602
    assert work.due_time.canonical_time_value == Fraction(259204, 3)
    assert await asyncio.wrap_future(main.submit_temporal_profile_migration(**args)) == receipt
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main._population_runtime_driver.clock.tick == 129600
    assert main.status_temporal_consumer.pending_work()[0] == work
    assert await asyncio.wrap_future(main.submit_temporal_profile_migration(**args)) == receipt
    await advance(172800)
    assert main.status_temporal_consumer.pending_work() == ()
    assert len([e for e in await _events(main) if e.event_type.endswith("expired")]) == 1
    await main._stop_population_runtime_on_shutdown()
    await start()
    await advance(172800)
    assert len([e for e in await _events(main) if e.event_type.endswith("expired")]) == 1
    record_property("migration_receipt", json.dumps(receipt.model_dump(mode="json")))


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["boundary", "mapping", "revision", "unit", "scope", "owner"])
async def test_invalid_activation_zero_write(application, fault):
    main, start, advance = application
    await start()
    await _apply(main, "timed", duration=86401)
    await advance(86400)
    args = request(main)
    if fault == "boundary": args["boundary"] = "render"
    if fault == "mapping": args["mapping"] = None
    if fault == "revision": args["expected_owner_revisions"] = {"gameplay:status_tags:actor:configured": 0}
    if fault == "unit": args["profile"] = replace(args["profile"], canonical_unit_ref="turn")
    if fault == "scope": args["mapping"] = replace(args["mapping"], target_timeline_ref="other")
    if fault == "owner": args["advancement_owner_ref"] = "role:model"
    before = main.gameplay_event_store.read_events()
    with pytest.raises(ValueError):
        await asyncio.wrap_future(main.submit_temporal_profile_migration(**args))
    assert main.gameplay_event_store.read_events() == before


@pytest.mark.asyncio
async def test_owner_receipt_survives_failed_completion_then_restart(application, monkeypatch):
    main, start, advance = application
    await start()
    await _apply(main, "timed", duration=86401)
    await advance(86400)
    args = request(main)
    from app.world_runtime import temporal_migration
    original = temporal_migration._append
    failed = False

    def fail_commit(driver, key, kind, payload):
        nonlocal failed
        if kind == "committed" and not failed:
            failed = True
            raise RuntimeError("injected_after_status_receipt")
        return original(driver, key, kind, payload)

    monkeypatch.setattr(temporal_migration, "_append", fail_commit)
    with pytest.raises(RuntimeError, match="injected_after_status_receipt"):
        await asyncio.wrap_future(main.submit_temporal_profile_migration(**args))
    events = await _events(main)
    assert len([event for event in events if event.event_type.endswith("time_migrated")]) == 1
    assert main._population_runtime_driver.clock.tick == 86400
    monkeypatch.setattr(temporal_migration, "_append", original)
    await main._stop_population_runtime_on_shutdown()
    await start()
    assert main._population_runtime_driver.clock.tick == 129600
    assert len([event for event in await _events(main) if event.event_type.endswith("time_migrated")]) == 1
    assert (await asyncio.wrap_future(main.submit_temporal_profile_migration(**args))).committed


@pytest.mark.asyncio
async def test_committed_receipt_repairs_failed_clock_activation(application, monkeypatch):
    main, start, advance = application
    await start()
    await _apply(main, "timed", duration=86401)
    await advance(86400)
    args = request(main)
    driver = main._population_runtime_driver
    original = driver.activate_migration
    monkeypatch.setattr(driver, "activate_migration", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("clock_fault")))
    with pytest.raises(RuntimeError, match="clock_fault"):
        await asyncio.wrap_future(main.submit_temporal_profile_migration(**args))
    assert driver.clock.tick == 86400
    monkeypatch.setattr(driver, "activate_migration", original)
    receipt = await asyncio.wrap_future(main.submit_temporal_profile_migration(**args))
    assert receipt.committed and driver.clock.tick == 129600
    assert len([e for e in await _events(main) if e.event_type.endswith("time_migrated")]) == 1
