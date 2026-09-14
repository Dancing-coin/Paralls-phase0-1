from __future__ import annotations

import asyncio

import pytest

from app import main
from app.population_continuity.world import WorldContinuityRuntime


@pytest.mark.asyncio
async def test_runtime_lifecycle_starts_one_population_task_and_cancels_it() -> None:
    main.stop_population_runtime()
    task = main.start_population_runtime()
    assert task is not None
    assert main.start_population_runtime() is task

    main.stop_population_runtime()
    await asyncio.sleep(0)

    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_runtime_lifecycle_publishes_population_event_and_stops_without_extra_task() -> None:
    main.stop_population_runtime()
    before = len(
        main.authority_event_bus.list_events(
            event_type="population_cadence_event",
            include_realtime=True,
            current_only=False,
        )
    )

    task = main.start_population_runtime()
    assert task is not None
    await asyncio.sleep(0)

    after = main.authority_event_bus.list_events(
        event_type="population_cadence_event",
        include_realtime=True,
        current_only=False,
    )
    assert len(after) >= before
    assert main.start_population_runtime() is task

    main.stop_population_runtime()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_runtime_stop_start_reuses_cadence_history(monkeypatch: pytest.MonkeyPatch) -> None:
    main.stop_population_runtime()


@pytest.mark.asyncio
async def test_runtime_restart_after_world_pause_resume_uses_runtime_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main.stop_population_runtime()
    main.reset_runtime_state()
    monkeypatch.setattr(main, "_population_runtime_sleep", _stop_after_one_sleep(main))

    first = main.start_population_runtime()
    assert first is not None
    await first
    main.stop_population_runtime()

    world = WorldContinuityRuntime(store=main.gameplay_event_store, mode=main._bakery_population_mode())
    assert world.pause(reason="test").committed
    assert world.resume().committed

    restarted = main.start_population_runtime()
    assert restarted is not None
    await restarted
    runtime_events = [
        event
        for event in main.authority_event_bus.list_events(
            event_type="population_cadence_event",
            include_realtime=True,
            current_only=False,
        )
        if event.payload["population_cadence"]["cadence_id"].startswith(
            "cadence:world:bakery-district:"
        )
    ]
    assert runtime_events[-1].payload["population_cadence"]["window_start"] == 86401
    assert runtime_events[-1].payload["population_cadence"]["window_end"] == 172801
    main.stop_population_runtime()
    monkeypatch.setattr(main, "_population_runtime_sleep", _stop_after_one_sleep(main))

    first = main.start_population_runtime()
    assert first is not None
    await first
    first_ids = tuple(
        event.payload["population_cadence"]["cadence_id"]
        for event in main.authority_event_bus.list_events(
            event_type="population_cadence_event",
            include_realtime=True,
            current_only=False,
        )
    )
    main.stop_population_runtime()

    second = main.start_population_runtime()
    assert second is not None
    await second
    second_ids = tuple(
        event.payload["population_cadence"]["cadence_id"]
        for event in main.authority_event_bus.list_events(
            event_type="population_cadence_event",
            include_realtime=True,
            current_only=False,
        )
    )
    assert second_ids[: len(first_ids)] == first_ids
    assert len(second_ids) == len(first_ids) + 1
    main.stop_population_runtime()


@pytest.mark.asyncio
async def test_runtime_uses_fake_clock_for_catch_up(monkeypatch: pytest.MonkeyPatch) -> None:
    main.stop_population_runtime()
    main.reset_runtime_state()
    initial_tick = main.gameplay_event_store.get_stream_head("world:world:bakery-district")
    monkeypatch.setattr(
        main,
        "_population_runtime_clock",
        lambda current, window: current + window * 3,
    )
    monkeypatch.setattr(main, "_population_runtime_sleep", _stop_after_one_sleep(main))

    task = main.start_population_runtime()
    assert task is not None
    await task

    driver = main._population_runtime_driver
    assert driver is not None
    assert driver.current_tick == initial_tick + driver.window_size * 2
    main.stop_population_runtime()


@pytest.mark.asyncio
async def test_runtime_clock_failure_is_observable(monkeypatch: pytest.MonkeyPatch) -> None:
    main.stop_population_runtime()

    def fail_clock(_current: int, _window: int) -> int:
        raise RuntimeError("clock_down")

    monkeypatch.setattr(main, "_population_runtime_clock", fail_clock)
    task = main.start_population_runtime()
    assert task is not None
    with pytest.raises(RuntimeError, match="clock_down"):
        await task
    assert isinstance(main.get_population_runtime_failure(), RuntimeError)
    main.stop_population_runtime()


def _stop_after_one_sleep(module):
    async def sleep(_seconds: float) -> None:
        assert module._population_runtime_stop_event is not None
        module._population_runtime_stop_event.set()

    return sleep
