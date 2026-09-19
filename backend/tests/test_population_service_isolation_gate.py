from copy import deepcopy
import asyncio

from scripts.verification.verify_population_service_isolation import evaluate, until, _writer_boundaries


def drained_process_state():
    return dict(status='ok', child_pid=101, process_generation='observed-generation',
        ipc_pending=0, ipc_capacity=128, pending_send=0, notification_capacity=128,
        runtime_pending=0, runtime_pending_capacity=128,
        transport_pending=0, transport_pending_capacity=128,
        execution_credit=dict(capacity=128, current=0, peak=3))


def valid_measurements():
    client = {"seconds": 120, "offered": {"health": 2400, "read": 600, "fact": 240, "dialogue": 12},
              "health_ms": [10.] * 2400, "accepted_ms": [10.] * 840, "business_ms": [20.] * 840,
              "fact_ms": [20.] * 240, "dialogue_ends": ["completed"] * 12, "errors": []}
    server = {"heartbeat_ms": [1.] * 12000, "window_ms": [100.] * 120,
              "max_lag_windows": 1, "final_backlog": 0, "queue_peak": 3,
              "owner_threads": [[101, 7]], "mutation_threads": [[101, 7]], "max_writers": 1,
              "provider_threads": [[101, 8]], "provider_calls": 12, "provider_max_active": 2,
              "windows_during_provider": 12, "errors": []}
    server.update(parent_pid=100, owner_pid=101, child_exit_code=0,
                  execution_credit=dict(capacity=128, current=0, peak=3),
                  parent_drained=drained_process_state(), parent_drained_at=130.,
                  parent_mutation_threads=[], parent_writer_calls={},
                  writer_boundaries=[name for _, _, name in _writer_boundaries()],
                  parent_writer_boundaries=[name for _, _, name in _writer_boundaries()],
                  asgi_lifecycle=dict(startup_failed=False, shutdown_failed=False, error_occurred=False))
    client.update(load_started_at=0., load_ended_at=120.)
    server.update(load_started_at=0., load_ended_at=120., heartbeat_expected_at=[i / 100 for i in range(12000)],
                  window_started_at=[float(i) for i in range(120)],
                  writer_calls={"gameplay_durable_append": 1, "heavenly_graph_batch": 1, "character_session_append_event": 1})
    return client, server


def test_service_gate_requires_complete_traffic_and_real_owner_and_provider_evidence():
    client, server = valid_measurements()
    assert evaluate(client, server)["passed"]
    for target, key, value in (("client", "fact_ms", [20.]), ("client", "health_ms", [10.]),
            ("client", "accepted_ms", [10.]), ("server", "provider_threads", [[101, 7]]),
            ("server", "mutation_threads", [[101, 7], [101, 8]]), ("server", "windows_during_provider", 0),
            ("server", "queue_peak", 129), ("server", "heartbeat_ms", [51.]),
            ("client", "health_ms", [-1.] * 2400),
            ("server", "window_ms", [801.] * 120), ("server", "final_backlog", 2)):
        c, s = deepcopy(client), deepcopy(server)
        (c if target == "client" else s)[key] = value
        assert not evaluate(c, s)["passed"], (target, key)


def test_absolute_schedule_rechecks_an_early_timer_wakeup(monkeypatch):
    from scripts.verification import verify_population_service_isolation as probe
    clock = [0.]
    waits = []
    async def wake_early(seconds):
        waits.append(seconds)
        clock[0] = .98 if len(waits) == 1 else 1.
    monkeypatch.setattr(probe, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(probe.asyncio, "sleep", wake_early)
    asyncio.run(until(1.))
    assert len(waits) == 2 and clock[0] >= 1.


def test_writer_probe_observes_real_durable_append_on_both_threads(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import ExitStack
    from threading import get_ident
    from os import getpid
    from app.gameplay.event_store import DurableGameplayEventStore
    from test_gameplay_event_store_contract import _batch, _event, _outbox
    from scripts.verification.verify_population_service_isolation import install_writer_probes

    calls = []
    def writer(name, original):
        def invoke(*args, **kwargs):
            calls.append((name, get_ident()))
            return original(*args, **kwargs)
        return invoke
    store = DurableGameplayEventStore(tmp_path / 'gameplay.sqlite3')
    with ExitStack() as stack:
        install_writer_probes(stack, writer)
        assert store.append_batch(_batch()).committed
        with ThreadPoolExecutor(max_workers=1) as pool:
            event = _event("evt:second", stream_id="other", tx="tx:second", command_id="cmd:second")
            batch = _batch(tx="tx:second", command_id="cmd:second", key="second", events=[event],
                           outbox_entries=[_outbox("evt:second", tx="tx:second")], expected={"other": 0})
            result = pool.submit(store.append_batch, batch).result()
            assert result.committed and result.resulting_stream_revisions == {"other": 1}
    durable = [tid for name, tid in calls if name == 'gameplay_durable_append']
    assert durable[0] == get_ident() and durable[1] != get_ident()
    client, server = valid_measurements()
    server.update(owner_threads=[[getpid(), get_ident()]], mutation_threads=[[getpid(), tid] for tid in sorted(set(durable))])
    assert not evaluate(client, server)["checks"]["single_writer"]


def test_drain_samples_cannot_dilute_load_window_percentile():
    from scripts.verification.verify_population_service_isolation import load_window_samples
    times = [i / 100 for i in range(12000)]
    values = [1.] * 11879 + [60.] * 121
    baseline = load_window_samples(values, times, 0., 120.)
    assert load_window_samples(values + [1.] * 300, times + [120. + i / 100 for i in range(300)], 0., 120.) == baseline
    assert baseline[-1] == 60.


def test_drain_does_not_change_gate_and_late_load_responses_still_count():
    client, server = valid_measurements()
    server["heartbeat_ms"] = [1.] * 11879 + [60.] * 121
    original = evaluate(client, server)
    assert original["metrics"]["heartbeat_p99_ms"] == 60.
    server["heartbeat_ms"].extend([1.] * 300)
    server["heartbeat_expected_at"].extend(120. + i / 100 for i in range(300))
    server["window_ms"].extend([100.] * 3)
    server["window_started_at"].extend([120., 121., 122.])
    assert evaluate(client, server) == original
    client["fact_ms"] = [16000.] * 240
    assert evaluate(client, server)["metrics"]["fact_p95_ms"] == 16000.
    server["load_ended_at"] = 123.
    assert not evaluate(client, server)["passed"]


def test_single_writer_requires_actual_durable_and_session_calls():
    client, server = valid_measurements()
    server["writer_calls"]["gameplay_durable_append"] = 0
    assert not evaluate(client, server)["checks"]["single_writer"]


def test_service_gate_requires_child_identities_and_zero_parent_writes():
    client, server = valid_measurements()
    assert evaluate(client, server)['passed']
    for field, value in [('owner_pid', 100), ('owner_pid', True), ('owner_threads', [7]),
            ('mutation_threads', [[100, 7]]), ('owner_threads', [[101, 7], [102, 7]]),
            ('provider_threads', [[100, 8]]), ('parent_mutation_threads', [[100, 9]]),
            ('parent_writer_calls', {'gameplay_durable_append': 1}),
            ('parent_writer_boundaries', []), ('child_exit_code', None), ('child_exit_code', True)]:
        changed = deepcopy(server)
        changed[field] = value
        assert not evaluate(client, changed)['passed'], field


def test_service_gate_requires_actual_complete_execution_credit():
    client, server = valid_measurements()
    for credit in [None, {}, {'capacity': 128, 'current': None, 'peak': None},
            {'capacity': 129, 'current': 0, 'peak': 3}, {'capacity': 128, 'current': 1, 'peak': 3},
            {'capacity': 128, 'current': 0, 'peak': 129}, {'capacity': 128, 'current': 0, 'peak': 2}]:
        changed = deepcopy(server)
        changed['execution_credit'] = credit
        assert not evaluate(client, changed)['passed'], credit


def test_service_gate_rejects_pending_or_misbound_pre_shutdown_snapshot():
    client, server = valid_measurements()
    for field, value in [('ipc_pending', 1), ('pending_send', 1), ('runtime_pending', 1),
            ('transport_pending', 1), ('runtime_pending', False), ('ipc_capacity', 129),
            ('runtime_pending_capacity', 129), ('transport_pending_capacity', 129),
            ('notification_capacity', None), ('child_pid', 102), ('status', 'unhealthy'),
            ('process_generation', '')]:
        changed = deepcopy(server)
        changed['parent_drained'][field] = value
        assert not evaluate(client, changed)['passed'], field
    for field, value in [('parent_drained', None), ('parent_drained_at', 119.),
                          ('parent_drained_at', float('nan'))]:
        changed = deepcopy(server)
        changed[field] = value
        assert not evaluate(client, changed)['passed'], field
    changed = deepcopy(server)
    changed['parent_drained']['execution_credit']['current'] = 1
    assert not evaluate(client, changed)['passed']


def test_service_waits_for_actual_pending_to_drain_before_sampling():
    from types import SimpleNamespace
    from scripts.verification.verify_population_service_isolation import wait_for_process_drain
    busy = dict(drained_process_state(), runtime_pending=1)
    calls = []
    def snapshot():
        calls.append(None)
        return busy if len(calls) == 1 else drained_process_state()
    assert asyncio.run(wait_for_process_drain(SimpleNamespace(snapshot=snapshot))) == drained_process_state()
    assert len(calls) == 2


def test_window_keeps_slow_completion_started_before_load_end():
    from scripts.verification.verify_population_service_isolation import load_window_samples
    assert load_window_samples([16000., 1.], [119.9, 120.1], 0., 120.) == [16000.]


def test_writer_probe_observes_real_character_session_commit(tmp_path):
    from contextlib import ExitStack
    from app.character_agent.storage.session_store import CharacterAgentSessionStore
    from scripts.verification.verify_population_service_isolation import install_writer_probes
    calls = []
    def writer(name, original):
        def invoke(*args, **kwargs):
            calls.append(name)
            return original(*args, **kwargs)
        return invoke
    store = CharacterAgentSessionStore(database_path=tmp_path / 'sessions.sqlite3')
    try:
        with ExitStack() as stack:
            install_writer_probes(stack, writer)
            store.append_event('char_a', 'test_event', 1, {})
        assert store.event_count('char_a') == 1
        assert 'character_session_append_event' in calls
    finally:
        store.close()


def test_raw_response_replay_separates_admission_from_original_business_ack():
    import pytest
    from scripts.verification.verify_population_service_isolation import replay_responses
    rows = []
    client = dict(seconds=1, load_started_at=10., health_ms=[], accepted_ms=[], business_ms=[], fact_ms=[], dialogue_ends=[])
    for ordinal in range(20):
        expected=10.+ordinal/20
        rows.append(dict(channel='health',key=ordinal,expected_at=expected,completed_at=expected+.01,status='ok'))
        client['health_ms'].append((expected+.01-expected)*1000)
    for kind, count in [('read',5),('fact',2),('dialogue',1)]:
        for ordinal in range(count):
            expected=10.+ordinal/count
            key=100+ordinal if kind=='fact' else f'service-dialogue:{ordinal}' if kind=='dialogue' else ordinal
            rows.append(dict(channel=kind,type='sent',ordinal=ordinal,producer_ts=100+ordinal,expected_at=expected,sent_at=expected))
            if kind=='dialogue':
                rows.append(dict(channel=kind,type='dialogue_stream_end',key=key,received_at=expected+.8,status='completed'))
                client['dialogue_ends'].append('completed')
                continue
            common=dict(channel=kind,key=key,request_id=f'service-{kind}:{ordinal}')
            rows.append(dict(common,type='runtime_admission',received_at=expected+.01,accepted=True))
            rows.append(dict(common,type='runtime_completion',received_at=expected+.8,status='owner_finished'))
            rows.append(dict(common,type='ack',received_at=expected+.8,accepted=True))
            client['accepted_ms'].append((expected+.01-expected)*1000)
            client['business_ms'].append((expected+.8-expected)*1000)
            if kind=='fact':
                rows.append(dict(common,type='spatial_access_runtime_state_snapshot',received_at=expected+.8))
                client['fact_ms'].append((expected+.8-expected)*1000)
    assert replay_responses(rows,client)['business_ms']==client['business_ms']
    for category, field, value in [('runtime_admission','request_id','other'),
            ('runtime_completion','status','accepted'), ('ack','accepted',False),
            ('runtime_admission','type','ack')]:
        changed=deepcopy(rows)
        next(row for row in changed if row.get('type')==category)[field]=value
        with pytest.raises(ValueError):replay_responses(changed,client)
    with pytest.raises(ValueError):
        replay_responses([row for row in rows if row.get('type')!='runtime_completion'],client)
    without_ack=deepcopy(client);without_ack['business_ms']=[]
    with pytest.raises(ValueError):
        replay_responses([row for row in rows if row.get('type')!='ack'],without_ack)
    for offset in [10., float('nan'), float('inf'), -.8]:
        changed=deepcopy(rows)
        first=next(row for row in changed if row.get('type')=='runtime_completion')
        first['received_at']+=offset
        with pytest.raises(ValueError):replay_responses(changed,client)


def test_service_gate_requires_original_business_ack_coverage():
    client,server=valid_measurements()
    client['business_ms']=[]
    assert not evaluate(client,server)['passed']


def test_service_gate_rejects_jointly_incomplete_unknown_or_duplicate_writer_boundaries():
    client, server = valid_measurements()
    for names in [['gameplay_durable_append'], ['made_up_writer'],
                  [*server['writer_boundaries'], server['writer_boundaries'][0]]]:
        changed = deepcopy(server)
        changed['writer_boundaries'] = changed['parent_writer_boundaries'] = names
        assert not evaluate(client, changed)['passed']


def test_actual_uvicorn_shutdown_failed_is_recorded_and_rejected(tmp_path, monkeypatch):
    import json
    from contextlib import ExitStack
    from types import SimpleNamespace
    import pytest
    from uvicorn import Config as RealConfig
    from uvicorn.lifespan.on import LifespanOn
    from scripts.verification import verify_population_service_isolation as probe
    from scripts.verification.population_godot_runner import write_json
    from test_population_service_evidence import process_records
    client, server = valid_measurements()
    server.update(population=100, window_size=1)
    _, owner, ready = process_records(server)
    with ExitStack() as stack:
        owner['writer_boundaries'] = probe.install_writer_probes(stack, lambda name, original: original)
    write_json(tmp_path / 'owner-ready.json', ready)
    write_json(tmp_path / 'owner-observed.json', owner)
    write_json(tmp_path / 'start', dict(load_started_at=0., load_ended_at=120.))
    clock = [0.]
    process = SimpleNamespace(pid=101, exitcode=None, is_alive=lambda: process.exitcode is None)
    host = SimpleNamespace(process=process, snapshot=drained_process_state)
    from app.services.runtime_asgi import RUNTIME_WEBSOCKET_PROTOCOL
    main = SimpleNamespace(RUNTIME_WEBSOCKET_PROTOCOL=RUNTIME_WEBSOCKET_PROTOCOL,
        app=SimpleNamespace(state=SimpleNamespace(runtime_process=host, process_qos=None)))
    async def asgi(scope, receive, send):
        assert (await receive())['type'] == 'lifespan.startup'
        await send({'type': 'lifespan.startup.complete'})
        assert (await receive())['type'] == 'lifespan.shutdown'
        await send({'type': 'lifespan.shutdown.failed', 'message': 'controlled_failure'})
    class Server:
        def __init__(self, config):
            self.started = self.should_exit = False
            self.lifespan = LifespanOn(RealConfig(asgi, lifespan='on', log_level='critical'))
        async def serve(self, sockets):
            await self.lifespan.startup()
            self.started = True
            while not self.should_exit:
                await asyncio.sleep(0)
            await self.lifespan.shutdown()
            process.exitcode = 0
    async def until(deadline):
        clock[0] = deadline
        if deadline >= 119.99:
            clock[0] = 120.
            (tmp_path / 'stop').touch()
        await asyncio.sleep(0)
    monkeypatch.setattr('uvicorn.Server', Server)
    monkeypatch.setattr('uvicorn.Config', lambda *a, **k: None)
    monkeypatch.setattr(probe, '_configure', lambda *a: (main, list(range(100)), 'unused'))
    monkeypatch.setattr(probe, 'perf_counter', lambda: clock[0])
    monkeypatch.setattr(probe, 'until', until)
    with pytest.raises(RuntimeError, match='service_asgi_lifecycle_failed'):
        asyncio.run(probe.backend(tmp_path))
    parent = json.loads((tmp_path / 'parent-observed.json').read_text())
    merged = json.loads((tmp_path / 'server.json').read_text())
    assert parent['asgi_lifecycle']['shutdown_failed'] is True
    assert 'service_asgi_lifecycle_failed' in parent['errors']
    assert merged['asgi_lifecycle'] == parent['asgi_lifecycle']
    assert not probe.evaluate(client, merged)['passed']
