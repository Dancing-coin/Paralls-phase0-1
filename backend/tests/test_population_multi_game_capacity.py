import asyncio
import json

import pytest

from scripts.verification import verify_population_multi_game_capacity as capacity


def test_capacity_requires_real_overlap_and_independent_games_not_four_game_performance(tmp_path, monkeypatch):
    source = {'files': {}}
    monkeypatch.setattr(capacity, 'identity', lambda _: source)
    groups = capacity.specifications()
    (tmp_path / 'manifest.json').write_text(json.dumps(dict(schema_version=1,
        profile='population-multi-game-capacity', base_commit='a'*40, source=source, groups=groups)))
    for group in groups:
        directory = tmp_path / group['directory']
        directory.mkdir()
        (directory / 'start.json').write_text(json.dumps(dict(origin=100, load_end=700)))
    for group in groups:
        (tmp_path / group['directory'] / 'collector-qos.json').write_text(json.dumps(dict(pid=123, supported=False, before=None, applied=None, restored=None)))
    manifest = json.loads((tmp_path / 'manifest.json').read_text())
    manifest['qos_artifacts'] = {group['directory'] + '/collector-qos.json': capacity.digest((tmp_path / group['directory'] / 'collector-qos.json').read_bytes()) for group in groups}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    fault = None
    def verify(path, **kwargs):
        ordinal = int(path.name.removeprefix('game-'))
        return dict(config=dict(population=1000, seconds=600, seed=30+ordinal, mode='one_x',
            provider_mode='live', capacity_metrics=True),
            integrity_passed=True, performance_passed=path.parent.name == '2-games',
            backend_pid=1 if fault == 'shared_pid' else ordinal,
            processes=dict(owner_pid=101 if fault == 'shared_owner' else 1 if fault == 'cross_role_pid' else ordinal+100),
            endpoint=dict(host='127.0.0.1', port=8000+(1 if fault == 'shared_port' else ordinal)),
            interval=dict(origin=101 if fault == 'short_overlap' and ordinal == 2 else 100, load_end=700),
            environment=dict(cpu='fixed'), windows=dict(metrics={}))
    monkeypatch.setattr(capacity, 'verify_case', verify)
    monkeypatch.setattr(capacity, 'resource_metrics', lambda path: dict(sqlite_io=dict(scope='logical_sqlite_io',
        databases={f'D:/captured/{path.parent.name}/{path.name}/state/{name}': {}
            for name in ('graph.sqlite3', 'graph.sqlite3.gameplay.json')})))
    report = capacity.verify_artifacts(tmp_path, expected_commit='a'*40)
    assert report['passed'] and report['groups'][0]['capacity_passed']
    assert not report['groups'][1]['capacity_passed']
    for fault in ('shared_pid', 'shared_owner', 'cross_role_pid', 'shared_port', 'short_overlap'):
        with pytest.raises(ValueError):
            capacity.verify_artifacts(tmp_path, expected_commit='a'*40)


def test_group_barrier_releases_all_ready_collectors_at_one_origin(tmp_path, monkeypatch):
    from time import perf_counter, sleep
    from scripts.verification import verify_population_mixed_soak as soak
    observed = []
    def collect(path, **config):
        path.mkdir()
        (path / 'prepared.json').write_text('{}')
        gate = config.pop('shared_start')
        deadline = perf_counter()+5
        while not gate.exists():
            assert perf_counter() < deadline
            sleep(.01)
        observed.append(asyncio.run(soak.read_control(gate)))
        return dict(collection_finished=True)
    monkeypatch.setattr(soak, 'collect', collect)
    capacity.collect_group(tmp_path / 'group', games=2, population=100, seconds=3, provider_mode='local_probe')
    assert len(observed) == 2 and observed[0] == observed[1]
    assert observed[0]['load_end'] == observed[0]['origin']+3


def test_capacity_io_uses_observed_sqlite_reads_not_database_file_size(tmp_path):
    from contextlib import closing
    import sqlite3
    from time import perf_counter, process_time
    from scripts.verification.population_benchmark_metrics import SqliteReadMeter
    with SqliteReadMeter() as meter, closing(sqlite3.connect(tmp_path / 'real.sqlite3')) as connection:
        connection.execute('CREATE TABLE values_read(value TEXT)')
        origin = perf_counter()
        start = dict(type='capacity_resources', phase='start', at=perf_counter(), cpu_seconds=process_time(), sqlite=meter.snapshot())
        window_start = perf_counter()
        connection.executemany('INSERT INTO values_read VALUES (?)', [('abc',)]*20)
        assert len(connection.execute('SELECT value FROM values_read').fetchall()) == 20
        window_end = perf_counter()
        end = dict(type='capacity_resources', phase='after_drain', at=perf_counter(), cpu_seconds=process_time(), sqlite=meter.snapshot())
    rows = [start, dict(type='window', started_at=window_start, finished_at=window_end),
        dict(type='drain', at=window_end, proven=True), end]
    (tmp_path / 'start').write_text(json.dumps(dict(origin=origin, load_end=window_end)))
    (tmp_path / 'server.json').write_text(json.dumps(dict(writer_calls={'original_store': 1}, max_writers=1, parent_pid=100)))
    parent_rows = [dict(type='resources', phase='start', at=start['at'], cpu_seconds=1., process_id=100),
        dict(type='resources', phase='after_drain', at=end['at'], cpu_seconds=4., process_id=100)]
    (tmp_path / 'parent.jsonl').write_text('\n'.join(json.dumps(row) for row in parent_rows)+'\n')
    def write_rows():
        (tmp_path / 'server.jsonl').write_text('\n'.join(json.dumps(row) for row in rows)+'\n')
    write_rows()
    report = capacity.resource_metrics(tmp_path)
    assert report['includes_tail_drain'] and report['writer_count'] == 1
    assert report['cpu_seconds_by_role']['parent'] == 3.
    assert report['cpu_seconds'] == end['cpu_seconds'] - start['cpu_seconds'] + 3.
    assert not report['sqlite_io']['physical_disk_bytes_measured']
    observed = next(iter(report['sqlite_io']['databases'].values()))
    assert observed['rows'] == 20 and observed['payload_bytes'] == 60
    # 两角色末资源都必须覆盖最后排空，不能只覆盖最后public窗口。
    rows[-2]['at'] = end['at'] + 40
    write_rows()
    with pytest.raises(ValueError, match='interval'):
        capacity.resource_metrics(tmp_path)
    end['at'] += 41
    write_rows()
    with pytest.raises(ValueError, match='parent_resource_interval'):
        capacity.resource_metrics(tmp_path)
    parent_rows[-1]['at'] = rows[-2]['at'] + .5
    (tmp_path / 'parent.jsonl').write_text('\n'.join(json.dumps(row) for row in parent_rows)+'\n')
    with pytest.raises(ValueError, match='parent_resource_interval'):
        capacity.resource_metrics(tmp_path)
    parent_rows[-1]['at'] = end['at']
    (tmp_path / 'parent.jsonl').write_text('\n'.join(json.dumps(row) for row in parent_rows)+'\n')
    assert capacity.resource_metrics(tmp_path)['includes_tail_drain']
    next(iter(end['sqlite']['databases'].values()))['statements'] = -1
    write_rows()
    with pytest.raises(ValueError):
        capacity.resource_metrics(tmp_path)


def test_failed_game_releases_other_collectors_waiting_on_barrier(tmp_path, monkeypatch):
    from time import perf_counter, sleep
    from scripts.verification import verify_population_mixed_soak as soak
    observed = []
    def collect(path, **config):
        path.mkdir()
        if path.name == 'game-1':
            raise ValueError('backend failed before ready')
        (path / 'prepared.json').write_text('{}')
        gate = config['shared_start']
        deadline = perf_counter()+5
        while not gate.exists():
            assert perf_counter() < deadline
            sleep(.01)
        observed.append(asyncio.run(soak.read_control(gate)))
        return dict(collection_finished=False)
    monkeypatch.setattr(soak, 'collect', collect)
    with pytest.raises(ValueError, match='capacity_backend_barrier_failed'):
        capacity.collect_group(tmp_path / 'group', games=2, population=100, seconds=3, provider_mode='local_probe')
    assert observed == [dict(abort=True)]


def test_two_actual_backends_share_interval_and_preserve_independent_sqlite(tmp_path):
    directory = tmp_path / 'actual'
    results = capacity.collect_group(directory, games=2, population=100, seconds=3, provider_mode='local_probe')
    assert all(row['collection_finished'] for row in results), results
    assert len({row['backend_pid'] for row in results}) == 2
    assert len({row['endpoint']['port'] for row in results}) == 2
    interval = json.loads((directory / 'start.json').read_text(encoding='utf-8'))
    for ordinal in (1, 2):
        path = directory / f'game-{ordinal}'
        assert json.loads((path / 'start').read_text(encoding='utf-8')) == interval
        resources = capacity.resource_metrics(path)
        assert resources['cpu_seconds'] > 0 and resources['writer_count'] == 1
        assert all(str(path) in key for key in resources['sqlite_io']['databases'])
        result = capacity.verify_case(path, expected_commit=results[ordinal-1]['base_commit'], require_formal=False)
        assert not result['passed'] and result['windows']['measured_windows'] == 3

@pytest.mark.parametrize('bad', ['shared', 'uri_shared', 'wrong_game'])
def test_capacity_database_identity_rejects_shared_or_foreign_main_stores(tmp_path, bad):
    paths = ['D:/captured/2-games/game-1/state/graph.sqlite3',
        'D:/captured/2-games/game-1/state/graph.sqlite3.gameplay.json']
    if bad == 'uri_shared':
        paths = ['file:///d:/CAPTURED/2-games/game-1/state/graph.sqlite3?mode=ro',
            r'd:\captured\2-games\game-1\state\graph.sqlite3.gameplay.json']
    resources = dict(sqlite_io=dict(databases={path: {} for path in paths}))
    with pytest.raises(ValueError, match='database'):
        capacity.database_identities(resources, tmp_path / '2-games/game-2')


def test_capacity_database_identity_preserves_moved_evidence_and_uri_aliases(tmp_path):
    resources = dict(sqlite_io=dict(databases={
        'file:///D:/old%20capture/2-games/game-1/state/graph.sqlite3?mode=ro': {},
        r'd:\OLD CAPTURE\2-games\game-1\state\graph.sqlite3': {},
        'D:/old capture/2-games/game-1/state/graph.sqlite3.gameplay.json': {}, ':memory:': {}}))
    root, identities = capacity.database_identities(resources, tmp_path / '2-games/game-1')
    assert root == 'd:/old capture'
    assert len(identities) == 2


def test_last_group_scope_failure_cannot_produce_green_matrix(tmp_path, monkeypatch):
    monkeypatch.setattr(capacity, 'identity', lambda _: {})
    def collect(path, *, games):
        path.mkdir()
        capacity.write_json(path / 'collector-qos.json', dict(pid=123, supported=False,
            before=None, applied=None, restored=None, error='OSError' if games == 4 else None))
        if games == 4:
            raise OSError('restore failed')
    monkeypatch.setattr(capacity, 'collect_group', collect)
    monkeypatch.setattr(capacity, 'verify_artifacts', lambda *a, **k: dict(passed=True))
    report = capacity.collect_matrix(tmp_path / 'new', expected_commit='a'*40)
    assert report['passed'] is False
    assert report['status'] == 'failed'
    assert report['errors']


def test_offline_matrix_rejects_recorded_scope_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(capacity, 'identity', lambda _: {})
    monkeypatch.setattr(capacity, 'specifications', lambda: [])
    capacity.write_json(tmp_path / 'manifest.json', dict(schema_version=1,
        profile='population-multi-game-capacity', base_commit='a'*40, source={}, groups=[],
        qos_artifacts={}, errors=[{'error': 'restore failed'}]))
    with pytest.raises(ValueError, match='capacity_collection_failed'):
        capacity.verify_artifacts(tmp_path, expected_commit='a'*40)
