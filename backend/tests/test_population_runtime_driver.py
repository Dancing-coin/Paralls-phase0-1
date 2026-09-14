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
