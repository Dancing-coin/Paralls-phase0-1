from __future__ import annotations

import asyncio
import sqlite3

import pytest

from app import main
from app.population_continuity.world import WorldContinuityRuntime


def test_persistent_runtime_moves_wal_checkpoints_to_one_owned_worker(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if sqlite3.sqlite_version_info < (3, 51, 3):
        pytest.skip("concurrent WAL checkpoint requires SQLite 3.51.3+")
    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "graph.sqlite3"))

    main.reset_runtime_state(restore_gameplay=True)
    worker = main._sqlite_wal_checkpoint_worker
    try:
        assert worker is not None
        assert worker.snapshot()["database_count"] == 3
        assert main.heavenly_graph._connection.execute(
            "PRAGMA wal_autocheckpoint"
        ).fetchone() == (0,)
        assert main.character_agent_runtime._session_store._connection.execute(
            "PRAGMA wal_autocheckpoint"
        ).fetchone() == (0,)
        assert main.gameplay_event_store._database_connection().execute(
            "PRAGMA wal_autocheckpoint"
        ).fetchone() == (0,)
        assert main.siming_audit_writer._connection.execute(
            "PRAGMA wal_autocheckpoint"
        ).fetchone() == (0,)
        runtime_connections = (
            main.heavenly_graph,
            main.character_agent_runtime._session_store,
            main.gameplay_event_store,
            main.siming_audit_writer,
        )
        for component in runtime_connections:
            connection = (
                component._database_connection()
                if hasattr(component, "_database_connection")
                else component._connection
            )
            assert connection.execute("PRAGMA cache_size").fetchone() == (
                -component._RUNTIME_CACHE_KIB,
            )
    finally:
        main.reset_runtime_state()

    assert not worker.is_alive()
    assert main._sqlite_wal_checkpoint_worker is None


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
    main.reset_runtime_state()

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

@pytest.mark.asyncio
async def test_production_lifecycle_assembles_and_closes_on_same_owner(tmp_path, monkeypatch):
    from threading import get_ident
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path / 'owner.sqlite3'))
    monkeypatch.setattr(main, '_population_runtime_sleep', _stop_after_one_sleep(main))
    seen = []
    original_reset = main._reset_runtime_state
    original_close = main.close_runtime_resources
    def reset(**kwargs):
        seen.append(('reset', get_ident()))
        return original_reset(**kwargs)
    def close():
        seen.append(('close', get_ident()))
        return original_close()
    monkeypatch.setattr(main, '_reset_runtime_state', reset)
    monkeypatch.setattr(main, 'close_runtime_resources', close)
    try:
        await main._start_population_runtime_on_startup()
        owner = main.runtime_execution
        task = main._population_runtime_task
        await main._start_population_runtime_on_startup()
        assert main.runtime_execution is owner
        assert main._population_runtime_task is task
        await task
        await main._stop_population_runtime_on_shutdown()
        assert seen[0][0] == 'reset' and seen[-1][0] == 'close'
        assert seen[0][1] == seen[-1][1] != get_ident()
        assert main.runtime_execution is None
    finally:
        await main._stop_population_runtime_on_shutdown()
        main.reset_runtime_state()


def test_health_exposes_runtime_failure(monkeypatch):
    monkeypatch.setattr(main, '_population_runtime_failure', RuntimeError('private details'))
    assert main.health()['status'] == 'unhealthy'
    assert 'private details' not in str(main.health())

@pytest.mark.asyncio
async def test_shutdown_timeout_retains_owner_and_rejects_second_start(tmp_path, monkeypatch):
    from threading import Event
    from app.services.runtime_execution import RuntimeStopped
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path / 'timeout.sqlite3'))
    monkeypatch.setattr(main, '_population_runtime_sleep', _stop_after_one_sleep(main))
    await main._start_population_runtime_on_startup()
    await main._population_runtime_task
    owner = main.runtime_execution
    entered, release = Event(), Event()
    def block():
        entered.set()
        release.wait(3)
    future = owner.submit(block)
    assert await asyncio.to_thread(entered.wait, 2)
    original_stop = owner.stop
    monkeypatch.setattr(owner, 'stop', lambda **_: original_stop(timeout_seconds=0.01))
    try:
        await main._stop_population_runtime_on_shutdown()
        assert main.runtime_execution is owner
        assert main.health()['status'] == 'unhealthy'
        with pytest.raises(RuntimeStopped):
            await main._start_population_runtime_on_startup()
    finally:
        release.set()
        await asyncio.wrap_future(future)
        monkeypatch.setattr(owner, 'stop', original_stop)
        await main._stop_population_runtime_on_shutdown()
        main.reset_runtime_state()


@pytest.mark.asyncio
async def test_failed_population_task_still_closes_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path / 'failed.sqlite3'))
    def fail_clock(current, window):
        raise ValueError('failed')
    monkeypatch.setattr(main, '_population_runtime_clock', fail_clock)
    await main._start_population_runtime_on_startup()
    try:
        with pytest.raises(ValueError):
            await main._population_runtime_task
        assert main.health()['status'] == 'unhealthy'
        await main._stop_population_runtime_on_shutdown()
        assert main.runtime_execution is None
    finally:
        await main._stop_population_runtime_on_shutdown()
        main.reset_runtime_state()

@pytest.mark.asyncio
@pytest.mark.parametrize('failure_stage', ['reset', 'build'])
async def test_startup_failure_closes_owner_without_shutdown_event(tmp_path, monkeypatch, failure_stage):
    from threading import get_ident
    from app.services.runtime_execution import RuntimeExecution, RuntimeStopped
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path / 'startup.sqlite3'))
    created, closed = [], []
    def create(**kwargs):
        owner = RuntimeExecution(**kwargs)
        created.append(owner)
        return owner
    original_reset = main._reset_runtime_state
    original_close = main.close_runtime_resources
    def fail_reset(**kwargs):
        original_reset(**kwargs)
        raise ValueError('startup_failed')
    def fail_build():
        raise ValueError('startup_failed')
    def close():
        closed.append(get_ident())
        original_close()
    monkeypatch.setattr(main, 'RuntimeExecution', create)
    monkeypatch.setattr(main, 'close_runtime_resources', close)
    monkeypatch.setattr(main, '_reset_runtime_state' if failure_stage == 'reset' else '_build_population_driver',
                        fail_reset if failure_stage == 'reset' else fail_build)
    try:
        with pytest.raises(ValueError, match='startup_failed'):
            await main._start_population_runtime_on_startup()
        assert main.runtime_execution is None
        assert created[0].closed.done()
        assert closed == [created[0]._owner]
        assert closed[0] != get_ident()
        with pytest.raises(RuntimeStopped):
            created[0].submit(get_ident)
        assert main.health()['status'] == 'unhealthy'
        from app.world_runtime.storage_lease import RuntimeStorageLease
        with RuntimeStorageLease(main.settings.heavenly_graph_path):
            pass
    finally:
        monkeypatch.setattr(main, '_reset_runtime_state', original_reset)
        await main._stop_population_runtime_on_shutdown()
        main.reset_runtime_state()

@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_startup', [False, True])
async def test_startup_cleanup_timeout_retains_owner_and_original_failure(tmp_path, monkeypatch, cancel_startup):
    from threading import Event
    from app.services.runtime_execution import RuntimeExecution, RuntimeStopped
    monkeypatch.setattr(main.settings, 'heavenly_graph_path', str(tmp_path / 'startup-timeout.sqlite3'))
    entered, release = Event(), Event()
    created = []
    def create(**kwargs):
        owner = RuntimeExecution(**kwargs)
        created.append(owner)
        original_stop = owner.stop
        monkeypatch.setattr(owner, 'stop', lambda **_: original_stop(timeout_seconds=0.01))
        return owner
    original_reset, original_close = main._reset_runtime_state, main.close_runtime_resources
    def reset(**kwargs):
        original_reset(**kwargs)
        if cancel_startup:
            entered.set()
            release.wait(3)
        else:
            raise ValueError('original_startup_failure')
    def close():
        if not cancel_startup:
            entered.set()
            release.wait(3)
        original_close()
    monkeypatch.setattr(main, 'RuntimeExecution', create)
    monkeypatch.setattr(main, '_reset_runtime_state', reset)
    monkeypatch.setattr(main, 'close_runtime_resources', close)
    task = asyncio.create_task(main._start_population_runtime_on_startup())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        if cancel_startup:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(ValueError, match='original_startup_failure'):
                await task
        assert main.runtime_execution is created[0]
        assert main.health()['status'] == 'unhealthy'
        with pytest.raises(RuntimeStopped):
            await main._start_population_runtime_on_startup()
        assert len(created) == 1
        with pytest.raises(RuntimeStopped):
            created[0].submit(lambda: None)
    finally:
        release.set()
        await asyncio.wrap_future(created[0].closed)
        monkeypatch.setattr(created[0], 'stop', RuntimeExecution.stop.__get__(created[0]))
        await main._stop_population_runtime_on_shutdown()
        monkeypatch.setattr(main, '_reset_runtime_state', original_reset)
        main.reset_runtime_state()
