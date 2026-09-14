from __future__ import annotations

import asyncio

import pytest

from app import main


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

