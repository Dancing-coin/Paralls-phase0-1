"""探针必须观察真实子进程中的原 owner，不用 parent 代理计数代替。"""
import asyncio
import json
import os
import sys
from time import perf_counter

from app.config import Settings
from app.services.runtime_process import RuntimeProcess
from scripts.verification.population_service_owner_probe import service_owner_child
from scripts.verification.population_godot_runner import write_json
from scripts.verification.verify_population_mixed_soak import read_control


def test_service_probe_observes_original_spawn_owner_and_real_windows(tmp_path, monkeypatch):
    import app.services.runtime_process as module
    monkeypatch.setattr(module, 'CHILD_TARGET', service_owner_child)
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--backend-child', str(tmp_path)])
    roster = tmp_path / 'roster.json'
    roster.write_text(json.dumps({'actor_ids': ['char_a', 'char_b', 'char_c']}), encoding='utf-8')
    settings = Settings(heavenly_graph_path=str(tmp_path / 'state/graph.sqlite3'),
        population_roster_path=str(roster), population_runtime_profile='benchmark_1x',
        dialogue_mode='stub', character_model_provider_kind='local', siming_llm_mode='disabled',
        character_model_endpoint=None, character_model_api_key=None, character_model_model=None)

    async def run():
        host = RuntimeProcess(settings.model_dump_json())
        async def read_when_ready(name):
            async with asyncio.timeout(20):
                while not (tmp_path / name).exists():
                    assert host.process.is_alive()
                    await asyncio.sleep(.02)
            return await read_control(tmp_path / name)
        try:
            await asyncio.wait_for(host.start(), 20)
            ready = await read_when_ready('owner-ready.json')
            assert ready['owner_pid'] == host.process.pid != os.getpid()
            assert ready['population'] == 3 and ready['window_size'] == 1
            origin = perf_counter() + .1
            write_json(tmp_path / 'start', dict(load_started_at=origin, load_ended_at=origin + 3))
            while perf_counter() < origin + 3:
                await asyncio.sleep(.02)
            (tmp_path / 'stop').touch()
            observed = await read_when_ready('owner-observed.json')
        finally:
            await host.close()
        assert host.process.exitcode == 0
        policy = json.loads((tmp_path / 'owner-qos.json').read_text(encoding='utf-8'))
        assert policy['pid'] == host.process.pid
        assert policy['restored'] == policy['before']
        if policy['supported']:
            assert policy['applied'][1] & 1 and not policy['applied'][2] & 1
        assert not observed['errors']
        assert observed['owner_threads'] == observed['mutation_threads']
        assert len(observed['owner_threads']) == 1
        assert observed['owner_threads'][0][0] == host.process.pid
        assert observed['writer_calls']['gameplay_durable_append'] > 0
        assert observed['writer_calls']['gameplay_outbox_delivered'] > 0
        assert observed['max_writers'] == 1
        assert len(observed['window_ms']) == len(observed['window_started_at']) >= 2
        assert observed['load_started_at'] == origin
        assert observed['load_ended_at'] == origin + 3
        assert all(value >= origin for value in observed['window_started_at'])
        # 没有发起模型输入；不能把这个窄真实启动用例当完整服务负载验收。
        assert observed['provider_calls'] == 0
    asyncio.run(run())
