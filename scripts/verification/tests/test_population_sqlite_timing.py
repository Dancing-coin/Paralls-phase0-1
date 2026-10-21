from contextlib import closing
import sqlite3

import pytest

from scripts.verification import population_benchmark_metrics as metrics
from scripts.verification import verify_population_mixed_soak as soak


@pytest.mark.parametrize('operation', [
    'execute', 'executemany', 'executescript', 'fetchone', 'fetchmany',
    'fetchall', 'next', 'commit', 'context_commit', 'context_rollback',
])
def test_slow_sqlite_diagnostic_preserves_real_operation_and_omits_data(tmp_path, monkeypatch, operation):
    # 丢失任一调用面会漏掉真实等待；SQL、参数或返回内容不应进入慢调用诊断。
    rows = []
    with metrics.SqliteReadMeter(slow_record=rows.append) as meter:
        with closing(sqlite3.connect(tmp_path / 'facts.sqlite3')) as connection:
            connection.execute('CREATE TABLE facts (value TEXT)')
            connection.executemany('INSERT INTO facts VALUES (?)', [('private-payload',), ('b',)])
            connection.commit()
            cursor = connection.execute('SELECT value FROM facts ORDER BY rowid')
            rows.clear()
            times = iter((10.0, 10.3))
            with monkeypatch.context() as timing:
                timing.setattr(metrics, 'perf_counter', lambda: next(times))
                if operation == 'execute':
                    result = cursor.execute('SELECT value FROM facts WHERE value=?', ('private-payload',))
                elif operation == 'executemany':
                    result = cursor.executemany('INSERT INTO facts VALUES (?)', [('c',), ('d',)])
                elif operation == 'executescript':
                    result = cursor.executescript("INSERT INTO facts VALUES ('c'); INSERT INTO facts VALUES ('d');")
                elif operation.startswith('fetch'):
                    result = getattr(cursor, operation)()
                elif operation == 'next':
                    result = next(cursor)
                elif operation == 'commit':
                    result = connection.commit()
                else:
                    connection.__enter__()
                    # BEGIN 在计时之外执行，保证 __exit__ 测到真正的事务收口。
                    timing.undo()
                    connection.execute("INSERT INTO facts VALUES ('temporary')")
                    timing.setattr(metrics, 'perf_counter', lambda: next(times))
                    result = connection.__exit__(None, None, None) if operation == 'context_commit' else (
                        connection.__exit__(ValueError, ValueError('private-failure'), None))

            assert len(rows) == 1
            row = rows[0]
            assert row['type'] == 'slow_sqlite'
            assert row['database'] == 'facts.sqlite3'
            assert row['operation'] == operation
            assert row['thread_id'] > 0
            assert row['started_at'] == 10.0
            assert row['finished_at'] == 10.3
            assert row['duration_ms'] == pytest.approx(300.0)
            assert row['error_type'] is None
            assert set(row) == {'type', 'database', 'operation', 'thread_id',
                                'started_at', 'finished_at', 'duration_ms', 'error_type'}
            assert 'private' not in str(row)
            if operation in {'execute', 'executemany', 'executescript'}:
                assert result is cursor
            elif operation in {'fetchone', 'next'}:
                assert result == ('private-payload',)
            elif operation in {'fetchmany', 'fetchall'}:
                assert result[0] == ('private-payload',)
            else:
                assert result is None or result is False
            if operation == 'context_rollback':
                assert connection.execute("SELECT COUNT(*) FROM facts WHERE value='temporary'").fetchone() == (0,)
            snapshot = meter.snapshot()['databases'][str(tmp_path / 'facts.sqlite3')]
            assert snapshot['statements'] >= 3
            if operation.startswith('fetch') or operation == 'next':
                assert snapshot['rows'] >= 1
                assert snapshot['payload_bytes'] >= len('private-payload')


def test_slow_sqlite_diagnostic_preserves_sqlite_error(tmp_path, monkeypatch):
    rows = []
    with metrics.SqliteReadMeter(slow_record=rows.append):
        with closing(sqlite3.connect(tmp_path / 'facts.sqlite3')) as connection:
            times = iter((10.0, 10.3))
            monkeypatch.setattr(metrics, 'perf_counter', lambda: next(times))
            with pytest.raises(sqlite3.OperationalError, match='no such table'):
                connection.execute('SELECT private_column FROM private_missing_table')
    assert len(rows) == 1
    assert rows[0]['error_type'] == 'OperationalError'
    assert 'private' not in str(rows[0])


def test_sqlite_diagnostic_ignores_fast_calls_and_has_no_timing_when_disabled(tmp_path, monkeypatch):
    rows = []
    with metrics.SqliteReadMeter(slow_record=rows.append):
        with closing(sqlite3.connect(tmp_path / 'facts.sqlite3')) as connection:
            times = iter((10.0, 10.249))
            with monkeypatch.context() as timing:
                timing.setattr(metrics, 'perf_counter', lambda: next(times))
                connection.execute('SELECT 1')
    assert rows == []

    with metrics.SqliteReadMeter():
        with closing(sqlite3.connect(':memory:')) as connection:
            monkeypatch.setattr(metrics, 'perf_counter', lambda: pytest.fail('disabled diagnostic read clock'))
            assert connection.execute('SELECT 1').fetchone() == (1,)


def test_capacity_sqlite_diagnostic_filters_startup_and_drain():
    # measurement 时间之外的慢调用不能混入正式容量窗口。
    rows = []
    record = soak.capacity_sqlite_recorder(rows.append, lambda: 100.0, 600)
    for started, finished in [(99.0, 99.4), (99.9, 100.3), (100.0, 100.3),
                              (699.7, 700.1), (700.0, 700.3)]:
        record(dict(type='slow_sqlite', started_at=started, finished_at=finished))
    assert [(row['started_at'], row['finished_at']) for row in rows] == [(100.0, 100.3), (699.7, 700.1)]
    assert all(row['phase'] == 'measurement' for row in rows)
    startup_rows = []
    soak.capacity_sqlite_recorder(startup_rows.append, lambda: None, 600)(
        dict(type='slow_sqlite', started_at=100.0, finished_at=100.3))
    assert startup_rows == []


@pytest.mark.parametrize('operation', ['failed_execute', 'commit', 'context_commit'])
def test_sqlite_callback_failure_preserves_native_error_and_durable_commit(tmp_path, monkeypatch, operation):
    # 日志错误不能替代真实 SQL 错误，也不能把已完成的提交变成调用失败。
    def failed_record(row):
        raise OSError('private-diagnostic-message')

    path = tmp_path / 'facts.sqlite3'
    with metrics.SqliteReadMeter(slow_record=failed_record) as meter:
        with closing(sqlite3.connect(path)) as connection:
            connection.execute('CREATE TABLE facts (value TEXT)')
            connection.execute('INSERT INTO facts VALUES (?)', ('committed-value',))
            times = iter((10.0, 10.3))
            with monkeypatch.context() as timing:
                timing.setattr(metrics, 'perf_counter', lambda: next(times))
                if operation == 'failed_execute':
                    with pytest.raises(sqlite3.OperationalError, match='no such table'):
                        connection.execute('SELECT private_column FROM private_missing_table')
                elif operation == 'commit':
                    assert connection.commit() is None
                else:
                    assert connection.__exit__(None, None, None) is False
            snapshot = meter.snapshot()
            assert snapshot['slow_record_failure'] == 'OSError'
            assert 'private' not in str(snapshot)
            if operation != 'failed_execute':
                assert not connection.in_transaction
                with closing(meter._original_connect(path)) as reader:
                    assert reader.execute('SELECT value FROM facts').fetchall() == [('committed-value',)]

        # 采集仍须失败闭合，不能因日志异常隔离而误报诊断完整。
        from scripts.verification.population_mixed_backend import merge_process_observations
        errors = []
        interval = dict(origin=100.0, load_end=700.0)
        parent = dict(parent_pid=1, owner_pid=2, population=1000, provider_mode='local_probe',
            interval=interval, child_exit_code=0, errors=[], writer_calls={}, writer_boundaries=[],
            asgi_lifecycle=dict(startup_failed=False, shutdown_failed=False, error_occurred=False))
        owner = dict(owner_pid=2, provider_mode='local_probe', interval=interval, errors=errors)
        ready = dict(owner_pid=2, population=1000)
        assert merge_process_observations(parent, owner, ready)['errors'] == []
        soak.capture_capacity_sqlite_failure(meter, errors)
        assert errors == ['sqlite_diagnostic_callback_failed:OSError']
        with pytest.raises(ValueError, match='mixed_process_observations_invalid'):
            merge_process_observations(parent, owner, ready)


def test_sqlite_callback_failure_state_keeps_default_snapshot_unchanged():
    errors = []
    with metrics.SqliteReadMeter() as meter:
        assert meter.snapshot() == dict(vm_interval=100, vm_steps_are_sampled=True, databases={})
        soak.capture_capacity_sqlite_failure(meter, errors)
        assert errors == []
    soak.capture_capacity_sqlite_failure(None, errors)
    assert errors == []


def _trigger_late_sqlite_callback_failure(meter, monkeypatch):
    def failed_record(row):
        raise OSError('private-late-diagnostic-message')

    meter.slow_record = failed_record
    with closing(sqlite3.connect(':memory:')) as connection:
        times = iter((10.0, 10.3, 10.4, 10.4))
        with monkeypatch.context() as timing:
            timing.setattr(metrics, 'perf_counter', lambda: next(times))
            assert connection.execute('SELECT 1').fetchone() == (1,)


def test_late_sqlite_callback_failure_is_collected_once(monkeypatch):
    # 首次排空汇总后才到达的失败须纳入终态，多次观察不能复制同一错误。
    errors = []
    with metrics.SqliteReadMeter() as meter:
        soak.capture_capacity_sqlite_failure(meter, errors)
        assert errors == []
        _trigger_late_sqlite_callback_failure(meter, monkeypatch)
        soak.capture_capacity_sqlite_failure(meter, errors)
        soak.capture_capacity_sqlite_failure(meter, errors)
    assert errors == ['sqlite_diagnostic_callback_failed:OSError']
