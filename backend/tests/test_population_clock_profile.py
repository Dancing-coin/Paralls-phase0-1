import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from app.world_runtime import population_driver
from app.world_runtime.population_driver import PopulationCadenceDriver
from test_population_runtime_driver import _event, _mode
from app.population_continuity.world import WorldContinuityRuntime
from app.gameplay.event_store import GameplayEventStore


@pytest.mark.asyncio
@pytest.mark.parametrize("period", [1.0, 0.1])
async def test_benchmark_waits_for_actual_deadline_and_never_preconfirms(period, monkeypatch):
    now = 10.0
    monkeypatch.setattr(population_driver, "monotonic", lambda: now)
    world = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    world.resume()
    published = []
    stop = asyncio.Event()

    def publish(cadence):
        nonlocal now
        published.append((cadence.window_end, now))
        now += period * .2  # 确认耗时应计入周期，不得额外再等完整period。
        return _event(cadence.cadence_id)

    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publish,
                                    window_size=1, catch_up_limit=2, wall_period_seconds=period)
    waits = []

    async def sleep(seconds):
        nonlocal now
        waits.append(seconds)
        if len(published) == 3:
            stop.set()
        else:
            now += seconds + 1e-9

    await driver.run_forever(stop, sleep)
    assert [tick for tick, _ in published] == [1, 2, 3]
    assert waits[0] == pytest.approx(period)
    assert waits[1:] == pytest.approx([period * .8] * 3, abs=1e-8)
    assert [when - 10 for _, when in published] == pytest.approx([period, period * 2, period * 3], abs=1e-8)


@pytest.mark.asyncio
async def test_benchmark_backlog_is_wall_due_and_pause_discards_old_debt(monkeypatch):
    now = 0.0
    monkeypatch.setattr(population_driver, "monotonic", lambda: now)
    world = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    world.resume()
    published = []
    stop = asyncio.Event()

    def publish(cadence):
        nonlocal now
        published.append(cadence.window_end)
        now += 2.5  # 第一窗口完成时已落后；下一poll追赶真实到期窗。
        return _event(cadence.cadence_id)

    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publish,
                                    window_size=1, catch_up_limit=2, wall_period_seconds=1)
    waits = []

    async def sleep(seconds):
        nonlocal now
        waits.append(seconds)
        if len(waits) == 1:
            now += seconds
        elif len(waits) == 2:
            assert published == [1] and seconds == 0
        elif len(waits) == 3:
            assert published == [1, 2, 3] and seconds == 0
            world.pause(reason="clock_test")
            world.resume()
            now += 100
        else:
            assert published == [1, 2, 3] and seconds == 1
            stop.set()

    await driver.run_forever(stop, sleep)


@pytest.mark.parametrize("period", [0, -1, float("nan"), float("inf")])
def test_invalid_wall_period_is_rejected(period):
    world = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    with pytest.raises(ValueError, match="population_driver_invalid"):
        PopulationCadenceDriver(world_runtime=world, publish_window=lambda _: None,
                                window_size=1, catch_up_limit=1, wall_period_seconds=period)


def test_named_profiles_pin_all_clock_fields_and_preserve_production():
    from app.world_runtime.simulation_clock import population_clock_profile
    assert population_clock_profile("production") == dict(simulation_tick_unit="second", window_ticks=86400,
                                                         wall_period_seconds=86400, speed=1)
    assert population_clock_profile("benchmark_1x") == dict(simulation_tick_unit="second", window_ticks=1,
                                                           wall_period_seconds=1, speed=1)
    assert population_clock_profile("benchmark_10x")["speed"] == 10
    with pytest.raises(ValueError, match="population_clock_profile_unknown"):
        population_clock_profile("arbitrary")


@pytest.mark.parametrize("profile, period", [("benchmark_1x", 1), ("benchmark_10x", .1)])
def test_main_assembly_uses_same_profile_for_mode_and_driver(profile, period, monkeypatch):
    from app import main
    monkeypatch.setattr(main.settings, "population_runtime_profile", profile)
    main.reset_runtime_state()
    try:
        driver = main._build_population_driver()
        assert driver is not None
        assert driver.window_size == 1 and driver.wall_period_seconds == period
        assert driver.world_runtime.mode == main._bakery_population_mode()
        assert driver.world_runtime.mode.revision.startswith("mode:bakery-district:v1:clock:sha256:")
    finally:
        main.close_runtime_resources()


@pytest.mark.parametrize("field, value", [("simulation_tick_unit", "minute"), ("window_ticks", 2),
                                         ("wall_period_seconds", 2), ("speed", 10)])
def test_any_clock_semantic_change_rejects_archive_recovery(tmp_path, monkeypatch, field, value):
    from app import main
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.population_continuity.roster import PopulationRoster
    from app.world_runtime.simulation_clock import population_clock_profile
    from test_population_durable_cadence_recovery import _publisher
    from app.services.authority_event_bus import InMemoryAuthorityEventBus

    monkeypatch.setattr(main.settings, "population_runtime_profile", "benchmark_1x")
    path = tmp_path / "world.sqlite3"
    roster = PopulationRoster(actor_ids=("resident",))
    world = WorldContinuityRuntime(store=DurableGameplayEventStore(path), mode=main._bakery_population_mode(), roster=roster)
    world.resume()
    publisher = _publisher(world, InMemoryAuthorityEventBus())
    assert publisher(world.build_population_cadence(window_start=0, window_end=1))
    changed = {**population_clock_profile("benchmark_1x"), field: value}
    monkeypatch.setattr(main, "population_clock_profile", lambda _: changed)
    restored = WorldContinuityRuntime(store=DurableGameplayEventStore(path), mode=main._bakery_population_mode(), roster=roster)
    with pytest.raises(ValueError, match="context|mode"):
        _publisher(restored, InMemoryAuthorityEventBus())


def test_fresh_process_main_lifespan_advances_three_real_seconds(tmp_path):
    code = """
import asyncio, json, time
from app import main
async def probe():
    await main._start_population_runtime_on_startup()
    try:
        owner = main.runtime_execution
        origin = await asyncio.wrap_future(owner.submit(lambda: main._population_runtime_driver.current_tick))
        started = time.monotonic()
        ticks = []
        while time.monotonic() - started < 8:
            tick = await asyncio.wrap_future(owner.submit(lambda: main._population_runtime_driver.current_tick))
            if tick > origin and (not ticks or ticks[-1][0] != tick):
                ticks.append([tick, time.monotonic() - started])
            if tick - origin >= 3:
                break
            await asyncio.sleep(.02)
        print('CLOCK_PROBE=' + json.dumps(dict(origin=origin, ticks=ticks)))
    finally:
        await main._stop_population_runtime_on_shutdown()
asyncio.run(probe())
"""
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=str(root / "backend"), PYTHONUTF8="1",
               PARALLS_HEAVENLY_GRAPH_PATH=str(tmp_path / "clock.sqlite3"),
               POPULATION_RUNTIME_PROFILE="benchmark_1x", CHARACTER_MODEL_PROVIDER_KIND="local",
               SIMING_LLM_MODE="disabled", CHARACTER_GRAPH_REQUIRE_CONTINUITY="0")
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stderr
    payload = json.loads(next(line.removeprefix("CLOCK_PROBE=") for line in result.stdout.splitlines()
                              if line.startswith("CLOCK_PROBE=")))
    assert [tick - payload["origin"] for tick, _ in payload["ticks"]] == [1, 2, 3]
    assert all(index - .02 <= elapsed < index + 1 for index, (_, elapsed) in enumerate(payload["ticks"], 1))


@pytest.mark.asyncio
@pytest.mark.parametrize('period', [1.0, 0.1])
async def test_resume_while_poll_is_queued_restarts_clock_at_observed_state(period, monkeypatch):
    from concurrent.futures import Future
    now = 0.0
    monkeypatch.setattr(population_driver, 'monotonic', lambda: now)
    world = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    world.resume()
    stop = asyncio.Event()
    published = []
    calls = 0

    class QueuedOwner:
        def submit(self, fn):
            nonlocal calls
            calls += 1
            future = Future()
            call = calls
            def execute():
                nonlocal now
                if call == 2:
                    now = 5.0
                    world.pause(reason='queued_poll')
                    world.resume()
                future.set_result(fn())
            asyncio.get_running_loop().call_soon(execute)
            return future

    def publish(cadence):
        published.append((cadence.window_end, now))
        return _event(cadence.cadence_id)
    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publish,
                                    window_size=1, catch_up_limit=1, wall_period_seconds=period)
    async def sleep(seconds):
        nonlocal now
        if published:
            stop.set()
        now += seconds + 1e-9
    await driver.run_forever(stop, sleep, execution=QueuedOwner())
    assert published == [(1, pytest.approx(5.0 + period, abs=1e-8))]


@pytest.mark.asyncio
@pytest.mark.parametrize('period', [1.0, 0.1])
@pytest.mark.parametrize('delay_ratio', [0.75, 1.5])
async def test_tail_cursor_queue_time_is_deducted_from_absolute_deadline(period, delay_ratio, monkeypatch):
    from concurrent.futures import Future
    now = 0.0
    monkeypatch.setattr(population_driver, 'monotonic', lambda: now)
    world = WorldContinuityRuntime(store=GameplayEventStore(), mode=_mode())
    world.resume()
    stop = asyncio.Event()
    published, waits = [], []
    calls = 0

    class QueuedOwner:
        def submit(self, fn):
            nonlocal calls
            calls += 1
            future = Future()
            call = calls
            def execute():
                nonlocal now
                if call == 4:
                    now += period * delay_ratio
                future.set_result(fn())
            asyncio.get_running_loop().call_soon(execute)
            return future

    def publish(cadence):
        published.append((cadence.window_end, now))
        return _event(cadence.cadence_id)
    driver = PopulationCadenceDriver(world_runtime=world, publish_window=publish,
                                    window_size=1, catch_up_limit=1, wall_period_seconds=period)
    async def sleep(seconds):
        nonlocal now
        waits.append((now, seconds))
        if published:
            stop.set()
        now += seconds + 1e-9
    await driver.run_forever(stop, sleep, execution=QueuedOwner())
    assert waits[0] == pytest.approx((period * delay_ratio, max(0.0, period * (1 - delay_ratio))))
    assert published == [(1, pytest.approx(period * max(1.0, delay_ratio), abs=1e-8))]
