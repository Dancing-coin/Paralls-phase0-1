"""生产 lifespan / 原真实时钟 / Social Owner 到 Character 子链。"""
import json
from pathlib import Path
import subprocess
import sys

from scripts.verification.population_godot_runner import child_environment


def test_main_social_wake_runs_durable_character_on_shared_pool(tmp_path):
    (tmp_path / 'roster.json').write_text(json.dumps(dict(actor_ids=['char_a', 'char_b', 'char_c', *[f'resident_{i:05d}' for i in range(97)]])), encoding='utf-8')
    code = '''
import asyncio, sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
from time import perf_counter
from scripts.verification.population_mixed_backend import configure
from scripts.verification.population_mixed_fixture import prepare_conflict_fixture
sys.path.insert(0, 'backend/tests')
from test_cognition_completion_revision import source_args
async def run():
    with ExitStack() as stack:
        main, actors, _ = configure(Path(sys.argv[1]), stack, mode='one_x', provider_mode='local_probe')
        start = main.start_population_runtime
        stack.enter_context(patch.object(main, 'start_population_runtime', lambda: None))
        async with main.component_app.router.lifespan_context(main.component_app):
            def prepare():
                rt = main.character_agent_runtime
                payload = source_args(rt, 'ingest_siming_output')['payload'].model_dump(mode='json')
                rt._l1.apply_siming_output(rt._plan_siming_entry(payload)['normalized_payload'])
                rt.set_background_mode('char_a', 'active')
                rt._refresh_weak_supervision_state(actor_id='char_a', producer_ts=0, reason_summary='private snapshot ready')
                wakes = prepare_conflict_fixture(store=main.gameplay_event_store, packages=main.production_package_registry,
                    policy_registry=main.production_social_policy_registry, profiles=rt._profile_registry,
                    actors=actors, key='production-character-wake')
                assert main._character_cognition_driver.slots is main._dialogue_provider_slots
                return wakes[0]
            wake = await asyncio.wrap_future(main.runtime_execution.submit(prepare))
            start()
            deadline = perf_counter()+15
            progress = None
            while perf_counter() < deadline:
                def read():
                    admissions = main._character_cognition_driver.coordinator.admissions
                    key = admissions.key_for(source_event_id=wake.source_event_id, actor_id=wake.actor_id, delivery_id=wake.candidate_key)
                    return admissions.read_progress(key)
                progress = await asyncio.wrap_future(main.runtime_execution.submit(read))
                if progress is not None and progress.status in {'completed', 'stale'}:
                    break
                assert main.get_population_runtime_failure() is None
                await asyncio.sleep(.02)
            assert progress is not None and progress.status == 'completed', progress
            assert progress.frame['background_result']['ran'] is True, progress.frame['background_result']
            assert progress.frame['commands'] == []
            assert progress.frame['source_kind'] == 'run_background_cognition_tick'
asyncio.run(run())
'''
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path)], cwd=Path(__file__).resolve().parents[2],
        env=child_environment(), capture_output=True, text=True, encoding='utf-8', timeout=35)
    assert result.returncode == 0, result.stderr


def test_character_loop_failure_still_closes_original_runtime_owner(monkeypatch):
    import asyncio
    from concurrent.futures import Future
    from types import SimpleNamespace
    import pytest
    from app import main
    stopped = []
    closed = Future()
    closed.set_result(None)
    execution = SimpleNamespace(stop=lambda **_: stopped.append(True) or True, closed=closed)
    async def no_population():
        pass
    async def fail_character():
        raise ValueError('character loop failed')
    monkeypatch.setattr(main, 'runtime_execution', execution)
    monkeypatch.setattr(main, 'websocket_transport_closers', {})
    monkeypatch.setattr(main, '_shutdown_population_runtime', no_population)
    monkeypatch.setattr(main, '_shutdown_character_cognition', fail_character)
    with pytest.raises(ValueError, match='character loop failed'):
        asyncio.run(main._stop_population_runtime_on_shutdown())
    assert stopped == [True] and main.runtime_execution is None
