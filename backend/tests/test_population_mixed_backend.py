import asyncio
import sqlite3
from time import perf_counter

import pytest

from scripts.verification.population_mixed_backend import hold_sqlite_busy


def test_mixed_owner_probe_uses_actual_spawn_fixture_driver_and_drain(tmp_path, monkeypatch):
    import os
    from scripts.verification import verify_population_mixed_soak as soak
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.population_mixed_fixture import RECIPE
    from app import config
    from app.services import runtime_process

    actors = ["char_a", "char_b", "char_c", *[f"resident_{i:05d}" for i in range(97)]]
    write_json(tmp_path / "roster.json", dict(actor_ids=actors))
    write_json(tmp_path / "run.json", dict(population=100, seconds=2, seed=7,
        mode="one_x", provider_mode="local_probe"))
    monkeypatch.setenv("PARALLS_MIXED_PROBE_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", soak.mixed_owner_child)
    settings = config.Settings(heavenly_graph_path=str(tmp_path / "state" / "graph.sqlite3"),
        population_roster_path=str(tmp_path / "roster.json"), population_runtime_profile="benchmark_1x",
        character_model_provider_kind="local", siming_llm_mode="disabled")

    async def scenario():
        host = runtime_process.RuntimeProcess(settings.model_dump_json())
        async def read_owner(name):
            async with asyncio.timeout(45):
                while not (tmp_path / name).exists():
                    assert host.process.is_alive()
                    await asyncio.sleep(.02)
            return await soak.read_control(tmp_path / name)
        try:
            await host.start()
            ready = await read_owner("owner-ready.json")
            assert ready["owner_pid"] == host.process.pid != os.getpid()
            assert ready["population"] == 100 and ready["mode"]["batch_limit"] == 36
            assert RECIPE in ready["mode"]["revision"]
            origin = perf_counter() + .1
            write_json(tmp_path / "start", dict(origin=origin, load_end=origin + 2))
            await asyncio.sleep(2.2)
            (tmp_path / "stop").touch()
            assert (await read_owner("owner-drained.json"))["errors"] == []
        finally:
            await host.close()
        assert host.process.exitcode == 0
        owner = await read_owner("owner-observed.json")
        assert owner["errors"] == [] and owner["owner_pid"] == host.process.pid
        final = await read_owner("final-state.json")
        assert final["drain"]["proven"] and soak.drain_complete(final["drain"])
        rows = (tmp_path / "server.jsonl").read_text(encoding="utf-8").splitlines()
        import json
        windows = [row for row in map(json.loads, rows) if row["type"] == "window"]
        assert len([row for row in windows if row["phase"] == "measurement"]) == 2
        assert all(row["result"]["b0_advanced_count"] == 100 for row in windows)

    asyncio.run(scenario())


def test_busy_fault_holds_real_writer_lock_for_two_seconds_without_blocking_loop(tmp_path):
    path = tmp_path / "gameplay.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE facts(value TEXT)")
        connection.execute("INSERT INTO facts VALUES ('original')")
    async def exercise():
        task = asyncio.create_task(hold_sqlite_busy(path))
        locked = False
        deadline = perf_counter() + 1
        while perf_counter() < deadline:
            with sqlite3.connect(path, timeout=0) as reader:
                assert reader.execute("SELECT value FROM facts").fetchall() == [("original",)]
                try:
                    reader.execute("BEGIN IMMEDIATE")
                except sqlite3.OperationalError as error:
                    assert "locked" in str(error)
                    locked = True
                finally:
                    reader.rollback()
            if locked:
                break
            await asyncio.sleep(.01)
        assert locked and not task.done()
        result = await task
        assert 2 <= result["released_at"] - result["acquired_at"] < 3
        with sqlite3.connect(path, timeout=0) as connection:
            connection.execute("INSERT INTO facts VALUES ('after')")
        return result
    asyncio.run(exercise())
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM facts").fetchall() == [("original",), ("after",)]


def test_busy_fault_does_not_create_a_missing_database(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        asyncio.run(hold_sqlite_busy(path))
    assert not path.exists()


def test_fresh_main_installs_fixture_package_and_budget_before_world_pins(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    from scripts.verification.population_godot_runner import child_environment
    (tmp_path / "roster.json").write_text(json.dumps(dict(actor_ids=["char_a", "char_b", "char_c",
        *[f"resident_{i:05d}" for i in range(97)]])), encoding="utf-8")
    code = '''
import asyncio, sys
from time import perf_counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from scripts.verification.population_mixed_backend import configure, MixedWindowProbe
from scripts.verification.population_mixed_fixture import RECIPE
from scripts.verification.population_mixed_load import MixedLoadSchedule
async def probe():
    with ExitStack() as stack:
        main, actors, secret = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode='local_probe')
        start = main.start_population_runtime
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        rows = []
        probe = MixedWindowProbe(main, MixedLoadSchedule(100, 7, 'one_x'), 1, rows.append)
        probe.install(stack)
        async with main.component_app.router.lifespan_context(main.component_app):
            def verify():
                driver = main._population_runtime_driver
                assert driver.current_tick == 0 and driver.window_size == 1 and driver.wall_period_seconds == 1
                assert driver.world_runtime.mode.batch_limit == 36
                assert RECIPE in driver.world_runtime.mode.revision
                assert len(main.production_package_registry.active_patch_set.patch_revision_ids) == 7
                assert main.character_agent_runtime._l2._gateway._provider._provider_kind == 'local'
                assert secret and len(actors) == 100
                probe.attach()
            await asyncio.wrap_future(main.runtime_execution.submit(verify))
            probe.origin = perf_counter()
            start()
            deadline = perf_counter() + 20
            while probe.latest is None:
                assert perf_counter() < deadline and main.get_population_runtime_failure() is None
                await asyncio.sleep(.02)
            main._population_runtime_stop_event.set()
            await main._population_runtime_task
            first = probe.latest
            assert first['previous_tick'] == 0 and first['sample']['confirmed_tick'] == 1
            assert first['result']['b0_advanced_count'] == 100
            assert first['cadence_ms'] >= 0 and first['fixture_ms'] > 0
            assert len(first['fixtures'][0]['rows']) == 28
            assert first['expected_at'] - probe.driver_origin == 1
            assert first['driver_started_at'] >= probe.driver_monotonic_origin + 1
            assert first['driver_finished_at'] >= first['driver_started_at']
            assert first['sample']['rss_bytes'] > 0
            assert first['sample']['caches']['publisher_records'] <= 2
            assert sum(row['type'] == 'driver_clock_origin' for row in rows) == 1
asyncio.run(probe())
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], cwd=root,
        env=child_environment(), capture_output=True, text=True, encoding="utf-8", timeout=40)
    assert result.returncode == 0, result.stderr


def test_busy_fault_repeated_cancel_waits_for_actual_sqlite_unlock(tmp_path):
    path = tmp_path / 'busy.sqlite3'
    sqlite3.connect(path).close()
    def locked():
        with sqlite3.connect(path, timeout=0) as connection:
            try:
                connection.execute('BEGIN IMMEDIATE')
            except sqlite3.OperationalError:
                return True
            finally:
                connection.rollback()
        return False
    async def exercise():
        task = asyncio.create_task(hold_sqlite_busy(path))
        deadline = perf_counter() + 1
        while not locked():
            assert perf_counter() < deadline
            await asyncio.sleep(.01)
        task.cancel()
        await asyncio.sleep(.02)
        task.cancel()
        await asyncio.sleep(.02)
        still_running = not task.done()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert still_running, 'cancel completed while worker still owns SQLite lock'
        assert not locked()
    asyncio.run(exercise())


@pytest.mark.parametrize('case', ['missing_key', 'disabled_order', 'route_key', 'stub_dialogue'])
def test_live_settings_require_actual_http_siming_route(case):
    from app.config import Settings, SimingLlmRouteSettings
    from scripts.verification.population_mixed_backend import validate_live_provider_settings
    settings = Settings(dialogue_mode='online', character_model_provider_kind='deepseek', character_model_api_key='test-only',
        character_model_endpoint='http://127.0.0.1/never-called', character_model_model='test',
        siming_llm_mode='http', siming_llm_api_key=None, siming_llm_provider_order=['openai_responses'])
    if case == 'disabled_order':
        settings = settings.model_copy(update=dict(siming_llm_api_key='test-only', siming_llm_provider_order=['disabled']))
    if case == 'route_key':
        settings = settings.model_copy(update=dict(siming_llm_routes=[SimingLlmRouteSettings(
            route_id='test', provider='openai_responses', api_key='route-only', endpoint='http://127.0.0.1/never-called', model='test')]))
        validate_live_provider_settings(settings)
    else:
        if case == 'stub_dialogue':
            settings = settings.model_copy(update=dict(dialogue_mode='stub', siming_llm_api_key='test-only'))
        with pytest.raises(ValueError, match='mixed_live_provider_configuration_required'):
            validate_live_provider_settings(settings)
