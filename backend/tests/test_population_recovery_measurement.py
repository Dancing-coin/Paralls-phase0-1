import importlib.util
from pathlib import Path
import sqlite3
import sys


def test_sqlite_meter_counts_all_fetch_surfaces_and_hidden_scan_work(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "scripts/verification/population_benchmark_metrics.py"
    spec = importlib.util.spec_from_file_location("recovery_metrics", path)
    metrics = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, metrics)
    spec.loader.exec_module(metrics)
    original = sqlite3.connect
    with metrics.SqliteReadMeter(vm_interval=10) as meter:
        connection = sqlite3.connect(":memory:")
        connection.execute("CREATE TABLE facts (value TEXT)")
        connection.executemany("INSERT INTO facts VALUES (?)", [("一",), ("b",), ("c",)])
        assert connection.execute("SELECT value FROM facts").fetchone() == ("一",)
        assert len(connection.cursor().execute("SELECT value FROM facts").fetchmany(2)) == 2
        assert len(connection.execute("SELECT value FROM facts").fetchall()) == 3
        assert len(list(connection.execute("SELECT value FROM facts"))) == 3
        before = meter.snapshot()["databases"][":memory:"]
        assert before["rows"] == 9
        assert before["payload_bytes"] == 17
        # 聚合只返回1行，VM计数仍应反映底层历史扫描，避免把LIMIT/COUNT误报为零成本。
        connection.execute("WITH RECURSIVE history(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM history WHERE n<10000) SELECT SUM(n) FROM history").fetchone()
        after = meter.snapshot()["databases"][":memory:"]
        assert after["rows"] == 10
        assert after["vm_steps_sampled"] > before["vm_steps_sampled"] + 10000
        connection.close()
    assert sqlite3.connect is original


def test_recovery_owner_probe_measures_original_startup_before_full_oracle(tmp_path, monkeypatch):
    """小档真实 spawn 验证计量边界，不代表万人长历史正式门禁。"""
    import asyncio
    import json
    import os
    import subprocess
    from app.config import Settings
    from app.services import runtime_process
    from scripts.verification import verify_population_long_session_recovery as gate
    from scripts.verification.verify_population_mixed_soak import read_control
    fixture = tmp_path / 'fixture'
    command = [sys.executable, str(Path(gate.__file__)), '--generate-child', str(fixture),
               '--population', '2', '--histories', '16', '--tail-windows', '1']
    generated = subprocess.run(command, cwd=gate.ROOT, capture_output=True, text=True, timeout=90)
    assert generated.returncode == 0, generated.stdout + generated.stderr
    output = tmp_path / 'result.json'
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--ready-child', str(output)])
    monkeypatch.setattr(runtime_process, 'CHILD_TARGET', gate.recovery_owner_child)
    settings = Settings(heavenly_graph_path=str(fixture / 'graph.sqlite3'),
        population_roster_path=str(fixture / 'roster.json'), population_runtime_profile='production',
        dialogue_mode='stub', character_model_provider_kind='local', siming_llm_mode='disabled',
        character_model_endpoint=None, character_model_api_key=None, character_model_model=None)

    async def run():
        host = runtime_process.RuntimeProcess(settings.model_dump_json())
        async def read(suffix):
            path = output.with_suffix(suffix)
            async with asyncio.timeout(30):
                while not path.exists():
                    assert host.process.is_alive()
                    await asyncio.sleep(.02)
            return await read_control(path)
        try:
            await host.start()
            ready = await read('.owner-ready.json')
            assert ready['owner_pid'] == host.process.pid != os.getpid()
            assert ready['restore_ms'] > 0 and ready['sql']['databases']
            assert not output.with_suffix('.owner-result.json').exists()
            output.with_suffix('.verify').touch()
            result = await read('.owner-result.json')
        finally:
            await host.close()
        assert host.process.exitcode == 0
        assert {key: value for key, value in result['ready'].items() if key != 'caches'} == ready
        assert result['verification_ms'] > 0
        expected = json.loads((fixture / 'oracle.json').read_text(encoding='utf-8'))
        assert gate.compare_oracles(result['oracle'], expected)['oracle_matches']
        assert all(value == 0 for value in result['ready']['caches']['gameplay'].values())
    asyncio.run(run())

    # 同一真实小档再走完整外层测量；Popen PID 必须就是实际 ASGI parent。
    measured = asyncio.run(gate.measure_process(fixture, fixture / 'result.json'))
    assert measured['oracle_matches']
    parent = json.loads((fixture / 'parent.json').read_text(encoding='utf-8'))
    assert measured['ready']['parent_pid'] == parent['pid']
    assert measured['ready']['owner_pid'] != parent['pid']

    for name in ('collector-qos.json', 'result.parent-qos.json', 'result.owner-qos.json'):
        policy = json.loads((fixture / name).read_text(encoding='utf-8'))
        assert policy['restored'] == policy['before']
        if policy['supported']:
            assert policy['applied'][1] & 1 and not policy['applied'][2] & 1
    generated = json.loads((fixture / 'manifest.json').read_text(encoding='utf-8'))['generation']
    assert generated['wall_ms'] > 0
    assert generated['process_qos']['restored'] == generated['process_qos']['before']
