"""混合采集目录独立复算：正式条件不可由摘要或本地 stub 冒充。"""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.verification import population_mixed_verification as verification
from scripts.verification import verify_population_mixed_soak as soak
from scripts.verification.population_godot_runner import child_environment


def test_siming_stale_pin_after_live_provider_is_a_safe_terminal_result():
    job = {
        'state': 'stale',
        'reason': 'stale_pin;missing_effects=',
        'source': {'event_id': 'event:1'},
    }
    call = {
        'family': 'siming',
        'source_event_ids': ['event:1'],
        'qualified_success': True,
    }
    assert verification.siming_job_finished_safely(job, [call])
    assert not verification.siming_job_finished_safely({**job, 'reason': 'wall_ttl_expired'}, [call])
    assert not verification.siming_job_finished_safely(job, [{**call, 'qualified_success': False}])

    timeout_job = {
        **job,
        'providers': [{
            'request_sha256': 'request:1',
            'source_event_id': 'event:1',
            'error': 'SimingLlmProviderTimeout',
        }],
    }
    timeout_call = {
        **call,
        'request_sha256': 'request:1',
        'error': 'SimingLlmProviderTimeout',
        'qualified_success': False,
    }
    assert verification.siming_job_finished_safely(timeout_job, [timeout_call])
    assert not verification.siming_job_finished_safely(timeout_job, [
        {**timeout_call, 'request_sha256': 'request:other'},
    ])
    assert not verification.siming_job_finished_safely(timeout_job, [
        {**timeout_call, 'source_event_ids': ['event:other']},
    ])


def test_actual_capture_offline_links_original_windows_sources_and_commits(tmp_path):
    directory = tmp_path / 'capture'
    child = subprocess.run([sys.executable, str(soak.ROOT / 'scripts/verification/verify_population_mixed_soak.py'),
        '--collect', str(directory), '--seconds', '3', '--population', '100', '--provider-mode', 'local_probe'],
        cwd=soak.ROOT, env=child_environment(), capture_output=True, text=True, encoding='utf-8', timeout=120)
    assert child.returncode == 0, child.stdout+child.stderr
    commit = soak.read(directory / 'manifest.json')['base_commit']
    result = verification.verify_case(directory, expected_commit=commit, require_formal=False)
    assert not result['passed'] and not result['checks']['live_configuration']
    assert result['authority']['b1_completed'] == 84 and result['checks']['authority_drained']
    assert result['checks']['runtime_drained']
    assert result['flow']['b2_expected'] == 2 and result['flow']['public_windows'] >= 4
    with pytest.raises(ValueError, match='formal'):
        verification.verify_case(directory, expected_commit=commit)
    # 即使重签 raw hash、声称通过，也不能把采集末态改成另一个 tick。
    final = soak.read(directory / 'final-state.json')
    final['confirmed_tick'] += 1
    (directory / 'final-state.json').write_text(json.dumps(final), encoding='utf-8')
    from scripts.verification.verify_population_service_isolation import raw_artifacts
    manifest = soak.read(directory / 'manifest.json')
    manifest.update(passed=True, raw_artifacts=raw_artifacts(directory))
    (directory / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        verification.verify_case(directory, expected_commit=commit, require_formal=False)

@pytest.mark.parametrize('offset', [-1000, 1000])
def test_window_clock_must_overlap_actual_load(offset):
    config = dict(population=100, seed=1, mode='one_x', seconds=3)
    rows = [dict(type='driver_clock_origin', at=10000+offset, monotonic=50),
        dict(type='window', finished_at=10002+offset, sample={'confirmed_tick':1})]
    with pytest.raises(ValueError, match='driver_load'):
        verification.temporal_evidence(rows, config, dict(origin=10000, load_end=10003),
            dict(origin=10000, load_end=10003, requests=[]), {'jobs':[]})


def test_sqlite_fault_is_bound_to_actual_handler_result():
    busy = dict(type='sqlite_busy', key='busy', acquired_at=1200., released_at=1202.)
    requests = [dict(key='busy', kind='sqlite_busy', ordinal=1, expected_at=1200., issued_at=1200.,
        finished_at=1202.1, status='handler_finished', result=dict(acquired_at=1200., released_at=1202.)),
        dict(key='release', kind='sqlite_release', ordinal=1, expected_at=1202., issued_at=1202.2,
        finished_at=1202.3, status='handler_finished', result=dict(acquired_at=1200., released_at=1202.))]
    verification._verify_sqlite_handler(busy, requests)
    with pytest.raises(ValueError):
        verification._verify_sqlite_handler(dict(busy, acquired_at=1., released_at=3.), requests)
    with pytest.raises(ValueError):
        verification._verify_sqlite_handler(busy, requests[:1])
    with pytest.raises(ValueError):
        verification._verify_sqlite_handler(busy, [dict(requests[0], issued_at=1200.5), requests[1]])


def test_process_proof_binds_raw_roles_and_counts_parent_memory_growth(tmp_path):
    from copy import deepcopy
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.population_mixed_backend import merge_process_observations
    from scripts.verification.verify_population_service_isolation import _writer_boundaries
    names = [name for _, _, name in _writer_boundaries()]
    config = dict(population=100, seconds=7200, provider_mode="local_probe")
    interval = dict(origin=100., load_end=7300.)
    ready = dict(owner_pid=200, population=100, mode={"revision": "fixture"})
    owner = dict(owner_pid=200, provider_mode="local_probe", errors=[], interval=interval,
        owner_threads=[[200, 4]], mutation_threads=[[200, 4]], writer_boundaries=names)
    parent = dict(parent_pid=100, owner_pid=200, population=100, child_exit_code=0, errors=[],
        interval=interval, provider_mode="local_probe", writer_boundaries=names, writer_calls={},
        asgi_lifecycle=dict(startup_failed=False, shutdown_failed=False, error_occurred=False))
    for name, value in (("owner-ready", ready), ("owner-observed", owner), ("parent-observed", parent),
            ("owner-drained", dict(owner_pid=200, errors=[]))):
        write_json(tmp_path / (name + ".json"), value)
    server = merge_process_observations(parent, owner, ready)
    state = dict(status="ok", child_pid=200, process_generation="one",
        ipc_pending=0, ipc_capacity=128, pending_send=0, notification_capacity=128,
        runtime_pending=0, runtime_pending_capacity=128, transport_pending=0, transport_pending_capacity=128,
        execution_credit=dict(capacity=128, current=0, peak=3))
    def sample(kind, at, **fields):
        return dict(type=kind, process_id=100, at=at, cpu_seconds=at/10, rss_bytes=20*1024*1024,
            runtime_process=state, **fields)
    samples = [sample("resources", 100., phase="start"),
        *[sample("heartbeat", 100.+ordinal*10, expected_at=100.+ordinal*10) for ordinal in range(1, 721)],
        sample("resources", 7301., phase="after_drain")]
    windows = [dict(type="window", process_id=200, phase="measurement", started_at=at-.2, finished_at=at,
        sample=dict(at=at, rss_bytes=100*1024*1024, cpu_seconds=at/5)) for at in (101., 1900., 6000., 7300.)]
    windows.extend(dict(type="heartbeat", process_id=200, expected_at=row["expected_at"], at=row["at"],
        rss_bytes=100*1024*1024) for row in samples if row["type"] == "heartbeat")
    windows.append(dict(type="drain", process_id=200, at=7300.5, proven=True))
    def save_parent():
        (tmp_path / "parent.jsonl").write_text("".join(json.dumps(row)+"\n" for row in samples), encoding="utf-8")
    save_parent()
    result = verification.process_evidence(tmp_path, config, server, windows, backend_pid=100, interval=interval)
    assert result["rss_growth_passed"] and result["parent_heartbeats"] == 720
    assert result["rss_growth"]["first_median_bytes"] == 120*1024*1024
    for row in samples:
        if row["at"] >= 5500:
            row["rss_bytes"] += 40*1024*1024
    save_parent()
    assert not verification.process_evidence(tmp_path, config, server, windows, backend_pid=100, interval=interval)["rss_growth_passed"]
    for change in ({"owner_pid": 201}, {"child_exit_code": True}, {"writer_calls": {names[0]: 1}},
            {"writer_boundaries": []}, {"asgi_lifecycle": dict(startup_failed=False, shutdown_failed=True, error_occurred=False)}):
        bad = dict(parent, **change)
        write_json(tmp_path / "parent-observed.json", bad)
        with pytest.raises(ValueError, match="process"):
            verification.process_evidence(tmp_path, config, server, windows, backend_pid=100, interval=interval)
    write_json(tmp_path / "parent-observed.json", parent)
    changed = deepcopy(windows)
    changed[0]["process_id"] = 100
    with pytest.raises(ValueError, match="process"):
        verification.process_evidence(tmp_path, config, server, changed, backend_pid=100, interval=interval)
    for key in ('ipc_pending', 'pending_send', 'runtime_pending', 'transport_pending', 'current'):
        samples[-1]['runtime_process'] = deepcopy(state)
        target = samples[-1]['runtime_process']['execution_credit'] if key == 'current' else samples[-1]['runtime_process']
        target[key] = 1
        save_parent()
        with pytest.raises(ValueError, match='process'):
            verification.process_evidence(tmp_path, config, server, windows, backend_pid=100, interval=interval)
    samples[-1]['runtime_process'] = state
    save_parent()
    late_drain = deepcopy(windows)
    late_drain[-1]['at'] = 7340.
    with pytest.raises(ValueError, match='process'):
        verification.process_evidence(tmp_path, config, server, late_drain, backend_pid=100, interval=interval)
    samples.pop(10)
    save_parent()
    with pytest.raises(ValueError, match="process"):
        verification.process_evidence(tmp_path, config, server, windows, backend_pid=100, interval=interval)


def test_heartbeat_uses_end_of_locked_observation():
    import threading
    from types import SimpleNamespace
    from time import perf_counter
    from app.services.runtime_execution import RuntimeExecution
    execution = RuntimeExecution()
    probe = SimpleNamespace(latest=None)
    entered, release = threading.Event(), threading.Event()
    def complete():
        with execution._lock:
            entered.set()
            assert release.wait(2)
            probe.latest = dict(sample={'confirmed_tick':1}, finished_at=perf_counter())
    owner = threading.Thread(target=complete)
    owner.start()
    assert entered.wait(2)
    timer = threading.Timer(.02, release.set)
    timer.start()
    row = soak.heartbeat_record(execution, SimpleNamespace(active=0), probe, expected_at=perf_counter())
    owner.join(2)
    timer.join()
    assert not owner.is_alive() and row['at'] >= probe.latest['finished_at']
    assert row['last_confirmed_tick'] == 1


def test_heartbeat_cannot_confirm_a_window_after_observation_end():
    config = dict(population=100, seed=1, mode='one_x', seconds=10)
    beat = dict(type='heartbeat', expected_at=110., at=110., last_confirmed_tick=1,
        execution={'failure':None, 'queue_depth':0}, provider_active=0)
    rows = [dict(type='driver_clock_origin', at=100., monotonic=50.), beat,
        dict(type='window', phase='measurement', started_at=101., finished_at=110.01, sample={'confirmed_tick':1})]
    with pytest.raises(ValueError, match='unconfirmed_tick'):
        verification.temporal_evidence(rows, config, dict(origin=100., load_end=110.),
            dict(origin=100., load_end=110., requests=[]), {'jobs':[]})
    rows[-1]['finished_at'] = 109.99
    assert verification.temporal_evidence(rows, config, dict(origin=100., load_end=110.),
        dict(origin=100., load_end=110., requests=[]), {'jobs':[]})['heartbeats'] == 1

def test_perf_measurement_segment_cannot_move_after_load_independently():
    config = dict(population=100, seed=1, mode='one_x', seconds=3)
    rows = [dict(type='driver_clock_origin', at=100., monotonic=50.),
        dict(type='window', phase='measurement', started_at=1101., finished_at=1102., sample={'confirmed_tick':1})]
    with pytest.raises(ValueError, match='measurement_load'):
        verification.temporal_evidence(rows, config, dict(origin=100., load_end=103.),
            dict(origin=100., load_end=103., requests=[]), {'jobs':[]})
    rows[-1].update(started_at=101., finished_at=105.)
    assert verification.temporal_evidence(rows, config, dict(origin=100., load_end=103.),
        dict(origin=100., load_end=103., requests=[]), {'jobs':[]})['heartbeats'] == 0


def test_parent_waits_for_actual_process_tail_and_rejects_unhealthy():
    import asyncio
    from types import SimpleNamespace
    async def run():
        state = dict(status='ok', ipc_pending=1, pending_send=1, runtime_pending=1, transport_pending=1,
            execution_credit=dict(current=1))
        host = SimpleNamespace(snapshot=lambda: state)
        waiter = asyncio.create_task(soak.wait_process_drain(host))
        await asyncio.sleep(.03)
        assert not waiter.done()
        for key in ('ipc_pending', 'pending_send', 'runtime_pending', 'transport_pending'):
            state[key] = 0
        await asyncio.sleep(.03)
        assert not waiter.done()
        state['execution_credit']['current'] = 0
        await asyncio.wait_for(waiter, 1)
        state['status'] = 'unhealthy'
        with pytest.raises(RuntimeError, match='process'):
            await soak.wait_process_drain(host)
    asyncio.run(run())


def test_parent_records_the_complete_observation_that_proved_drain(monkeypatch):
    import asyncio
    import io
    import json
    from types import SimpleNamespace
    from scripts.verification import population_benchmark_metrics as metrics

    calls = []
    def snapshot():
        calls.append(True)
        # 后台轮询可以在合格观察之后重新占用额度，不能据第二次观察改写排空证据。
        return dict(status='ok', ipc_pending=0, pending_send=0, runtime_pending=0, transport_pending=0,
            execution_credit=dict(current=0 if len(calls) == 1 else 1))
    monkeypatch.setattr(metrics, 'current_rss_bytes', lambda: 12345)
    monkeypatch.setattr(soak, 'process_time', lambda: 3.)
    monkeypatch.setattr(soak, 'perf_counter', lambda: 42.)
    host = SimpleNamespace(snapshot=snapshot)
    row = asyncio.run(soak.wait_process_drain(host))
    assert len(calls) == 1
    assert row is not None
    assert row['type'] == 'resources' and row['phase'] == 'after_drain'
    assert row['rss_bytes'] == 12345 and row['cpu_seconds'] == 3. and row['at'] == 42.
    assert row['process_id'] == soak.os.getpid()
    assert host.snapshot()['execution_credit']['current'] == 1
    output = io.StringIO()
    soak.jsonl_writer(output)(row)
    assert json.loads(output.getvalue())['runtime_process']['execution_credit']['current'] == 0
