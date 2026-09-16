from __future__ import annotations

import asyncio

import pytest

from app import main
from app.population_continuity.world import WorldContinuityRuntime


@pytest.mark.asyncio
async def test_runtime_lifecycle_starts_one_population_task_and_cancels_it(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "graph.sqlite3"))
    main.reset_runtime_state(restore_gameplay=True)
    try:
        task = main.start_population_runtime()
        assert task is not None
        assert main.start_population_runtime() is task

        main.stop_population_runtime()
        await asyncio.sleep(0)

        assert task.cancelled() or task.done()
    finally:
        await main._shutdown_population_runtime()
        main.reset_runtime_state()


@pytest.mark.asyncio
async def test_runtime_lifecycle_publishes_population_event_and_stops_without_extra_task(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "graph.sqlite3"))
    main.reset_runtime_state(restore_gameplay=True)
    try:
        before = len(main.authority_event_bus.list_events(
            event_type="population_cadence_event",
            include_realtime=True,
            current_only=False,
        ))

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
    finally:
        await main._shutdown_population_runtime()
        main.reset_runtime_state()


@pytest.mark.asyncio
async def test_runtime_stop_start_reuses_cadence_history(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "graph.sqlite3"))
    main.reset_runtime_state(restore_gameplay=True)
    monkeypatch.setattr(main, "_population_runtime_sleep", _stop_after_one_sleep(main))
    try:
        first = main.start_population_runtime()
        assert first is not None
        await first
        first_ids = tuple(
            event.payload["cadence"]["cadence_id"]
            for event in main.gameplay_event_store.read_stream(
                "population-cadence:world:bakery-district"
            )
        )
        main.stop_population_runtime()

        second = main.start_population_runtime()
        assert second is not None
        await second
        second_ids = tuple(
            event.payload["cadence"]["cadence_id"]
            for event in main.gameplay_event_store.read_stream(
                "population-cadence:world:bakery-district"
            )
        )
        assert second_ids[: len(first_ids)] == first_ids
        assert len(second_ids) == len(first_ids) + 1
    finally:
        await main._shutdown_population_runtime()
        main.reset_runtime_state()


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
    assert runtime_events[-1].payload["population_cadence"]["window_start"] == 86400
    assert runtime_events[-1].payload["population_cadence"]["window_end"] == 172800
    main.stop_population_runtime()


@pytest.mark.asyncio
async def test_runtime_uses_fake_clock_for_catch_up(monkeypatch: pytest.MonkeyPatch) -> None:
    main.stop_population_runtime()
    main.reset_runtime_state()
    initial_tick = 0
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


@pytest.mark.asyncio
async def test_application_reopens_persistent_store_and_resumes_without_reseeding(tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "graph.sqlite3"))
    monkeypatch.setattr(main, "_population_runtime_sleep", _stop_after_one_sleep(main))
    try:
        main.reset_runtime_state(restore_gameplay=True)
        await main.start_population_runtime()
        initial_events = main.gameplay_event_store.get_last_global_sequence()
        rows = main._population_runtime_driver.world_runtime.population_hot_state.export_rows()
        main.stop_population_runtime()
        main.reset_runtime_state(restore_gameplay=True)
        assert main.gameplay_event_store.get_last_global_sequence() == initial_events
        task = main.start_population_runtime()
        assert main._population_runtime_driver.current_tick == 86400
        assert main._population_runtime_driver.world_runtime.population_hot_state.export_rows() == rows
        await task
        assert main._population_runtime_driver.current_tick == 172800
        assert main.gameplay_event_store.get_last_global_sequence() == initial_events + 1
    finally:
        await main._shutdown_population_runtime()
        main.reset_runtime_state()
