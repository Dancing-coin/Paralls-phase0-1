from __future__ import annotations

import asyncio

import pytest

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.population_continuity.models import WorldModeProfile
from app.population_continuity.world import WorldContinuityRuntime
from app.gameplay.event_store import GameplayEventStore
from app.world_runtime.population_driver import PopulationCadenceDriver


def _mode() -> WorldModeProfile:
    return WorldModeProfile(
        world_ref="world",
        mode="simulation",
        revision="mode:v1",
        cadence_class="hourly",
        batch_limit=3,
        wake_budget=3,
        catch_up_limit=2,
        degraded_threshold=20,
    )


def _event(cadence_id: str) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=f"event:{cadence_id}",
        event_type="population_cadence_event",
        producer_ts=0,
        room_id="room",
        scene_id="scene",
        zone_id="zone",
        source=AuthorityEventSource(layer="L2", system="test"),
        routing=AuthorityEventRouting(audience_mode="broadcast", routing_mode="event_type"),
        priority="p2",
        durability="realtime",
        causation_id="cause",
        correlation_id="corr",
        payload={"population_cadence": {"cadence_id": cadence_id}},
    )


@pytest.fixture
def driver() -> PopulationCadenceDriver:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    published: list[AuthorityEvent] = []

    def publish(cadence):
        event = _event(cadence.cadence_id)
        published.append(event)
        return event

    publish.published_events = published
    return PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=publish,
        window_size=3600,
        catch_up_limit=2,
        initial_tick=0,
    )


def test_driver_publishes_each_due_window_once(driver: PopulationCadenceDriver) -> None:
    first = driver.tick(14400)
    second = driver.tick(14400)

    assert first.published_cadence_ids == ("cadence:world:0", "cadence:world:3600")
    assert first.deferred_windows == ("cadence:world:7200", "cadence:world:10800")
    assert second.published_cadence_ids == ("cadence:world:7200", "cadence:world:10800")


def test_driver_does_not_publish_partial_future_window(driver: PopulationCadenceDriver) -> None:
    result = driver.tick(1000)

    assert result.published_cadence_ids == ()
    assert result.deferred_windows == ()
    assert driver.current_tick == 0


def test_driver_resumes_from_last_complete_window_after_partial_target(driver: PopulationCadenceDriver) -> None:
    first = driver.tick(4000)
    first_cursor = driver.current_tick
    second = driver.tick(7600)

    assert first.published_cadence_ids == ("cadence:world:0",)
    assert first_cursor == 3600
    assert second.published_cadence_ids == ("cadence:world:3600",)


def test_zero_catch_up_budget_keeps_due_windows_for_next_tick() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    driver = PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=lambda cadence: _event(cadence.cadence_id),
        window_size=3600,
        catch_up_limit=0,
        initial_tick=0,
    )

    result = driver.tick(3600)

    assert result.published_cadence_ids == ()
    assert result.deferred_windows == ("cadence:world:0",)
    assert driver.current_tick == 0


def test_driver_rebuild_uses_existing_publisher_history(driver: PopulationCadenceDriver) -> None:
    driver.tick(3600)
    rebuilt = PopulationCadenceDriver(
        world_runtime=driver.world_runtime,
        publish_window=driver.publish_window,
        window_size=3600,
        catch_up_limit=2,
        initial_tick=0,
    )

    result = rebuilt.tick(3600)

    assert result.published_cadence_ids == ()
    assert rebuilt.current_tick == 3600
    assert rebuilt.tick(7200).published_cadence_ids == ("cadence:world:3600",)


def test_driver_reports_selected_windows_after_publisher_failure() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    calls = 0

    def publish(cadence):
        nonlocal calls
        calls += 1
        return _event(cadence.cadence_id) if calls == 1 else None

    driver = PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=publish,
        window_size=3600,
        catch_up_limit=3,
        initial_tick=0,
    )

    result = driver.tick(10800)

    assert result.published_cadence_ids == ("cadence:world:0",)
    assert result.rejected_windows == (("cadence:world:3600", "publisher_rejected"),)
    assert result.deferred_windows == ("cadence:world:7200",)
    assert driver.current_tick == 3600


def test_driver_does_not_publish_while_world_is_paused() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    runtime.pause(reason="test")
    driver = PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=lambda cadence: _event(cadence.cadence_id),
        window_size=3600,
        catch_up_limit=2,
        initial_tick=0,
    )

    paused = driver.tick(7200)

    assert paused.published_cadence_ids == ()
    assert paused.deferred_windows == ("cadence:world:0", "cadence:world:3600")
    assert driver.current_tick == 0

    runtime.resume()
    resumed = driver.tick(7200)
    assert resumed.published_cadence_ids == ("cadence:world:0", "cadence:world:3600")


def test_driver_rejects_rewind() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    driver = PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=lambda cadence: _event(cadence.cadence_id),
        window_size=3600,
        catch_up_limit=2,
        initial_tick=3600,
    )

    result = driver.tick(0)

    assert result.rejected_windows == (("cadence:world:0", "simulation_clock_cannot_rewind"),)


def test_driver_keeps_rejected_window_due_when_publisher_returns_none() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()
    driver = PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=lambda cadence: None,
        window_size=3600,
        catch_up_limit=2,
        initial_tick=0,
    )

    result = driver.tick(3600)

    assert result.published_cadence_ids == ()
    assert result.rejected_windows == (("cadence:world:0", "publisher_rejected"),)
    assert driver.current_tick == 0


def test_driver_returns_auditable_rejection_for_publisher_exception() -> None:
    runtime = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    runtime.resume()

    def publish(_cadence):
        raise RuntimeError("publisher_down")

    driver = PopulationCadenceDriver(
        world_runtime=runtime,
        publish_window=publish,
        window_size=3600,
        catch_up_limit=2,
        initial_tick=0,
    )

    result = driver.tick(3600)

    assert result.rejected_windows == (("cadence:world:0", "publisher_exception:RuntimeError:publisher_down"),)
    assert driver.current_tick == 0


@pytest.mark.asyncio
async def test_driver_run_forever_ticks_until_stopped(driver: PopulationCadenceDriver) -> None:
    stop = asyncio.Event()
    calls = 0

    async def sleep(_seconds: float) -> None:
        nonlocal calls
        calls += 1
        stop.set()

    await driver.run_forever(stop, sleep)

    assert calls == 1


@pytest.mark.asyncio
async def test_window_period_includes_processing_time(driver, monkeypatch):
    from app.world_runtime import population_driver

    values = iter((0.0, 0.0, 12.0))
    monkeypatch.setattr(population_driver, "monotonic", lambda: next(values))
    stop = asyncio.Event()
    waits = []

    async def sleep(seconds):
        waits.append(seconds)
        stop.set()

    await driver.run_forever(stop, sleep)
    assert waits == [3588.0]

@pytest.mark.asyncio
async def test_execution_dispatch_yields_between_windows_and_honors_pause(driver):
    from app.services.runtime_execution import RuntimeExecution
    from threading import get_ident
    execution = RuntimeExecution()
    stop = asyncio.Event()
    calls = []
    original = driver.publish_window
    def publish(cadence):
        calls.append(get_ident())
        event = original(cadence)
        driver.world_runtime.pause(reason='boundary')
        return event
    driver.publish_window = publish
    async def sleep(_):
        stop.set()
    try:
        await driver.run_forever(stop, sleep, lambda current, window: current + 3 * window, execution=execution)
        assert len(calls) == 1
        assert calls[0] != get_ident()
        assert driver.current_tick == 3600
    finally:
        assert execution.stop(timeout_seconds=2)


@pytest.mark.asyncio
async def test_async_driver_failure_is_raised_without_advancing(driver):
    driver.publish_window = lambda cadence: None
    stop = asyncio.Event()
    async def sleep(_):
        stop.set()
    with pytest.raises(RuntimeError, match='population_window_failed'):
        await driver.run_forever(stop, sleep)
    assert driver.current_tick == 0

@pytest.mark.asyncio
async def test_pause_resume_between_polls_does_not_catch_up_wall_time(driver, monkeypatch):
    from app.world_runtime import population_driver
    values = iter((0.0, 0.0, 0.0, 360000.0, 360000.0))
    monkeypatch.setattr(population_driver, 'monotonic', lambda: next(values))
    stop = asyncio.Event()
    sleeps = 0
    async def sleep(_):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 1:
            driver.world_runtime.pause(reason='test')
            driver.world_runtime.resume()
        else:
            stop.set()
    await driver.run_forever(stop, sleep)
    assert driver.current_tick == 7200

@pytest.mark.asyncio
async def test_pause_resume_at_window_boundary_discards_old_catch_up_target(driver):
    driver.catch_up_limit = 3
    stop = asyncio.Event()
    original = driver.publish_window
    published = []
    def transition():
        driver.world_runtime.pause(reason='window-boundary')
        driver.world_runtime.resume()
    def publish(cadence):
        published.append(cadence.cadence_id)
        if len(published) == 1:
            asyncio.get_running_loop().call_soon(transition)
        return original(cadence)
    driver.publish_window = publish
    async def sleep(_):
        stop.set()
    await driver.run_forever(stop, sleep, lambda current, window: current + 3 * window)
    assert published == ['cadence:world:0']
    assert driver.current_tick == 3600
