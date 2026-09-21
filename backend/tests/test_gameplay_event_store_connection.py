"""连接复用不得改变原事务可见性、崩溃恢复和资源关闭边界。"""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore, GameplayEventStoreSnapshotError
from test_gameplay_event_store_contract import _batch, _event, _outbox


def _single_batch(*, suffix: str, stream_id: str) -> dict[str, object]:
    tx = f"tx:group:{suffix}"
    command = f"cmd:group:{suffix}"
    event_id = f"evt:group:{suffix}"
    return _batch(
        tx=tx,
        command_id=command,
        key=f"key:group:{suffix}",
        digest=f"digest:group:{suffix}",
        events=[_event(event_id, stream_id=stream_id, tx=tx, command_id=command)],
        outbox_entries=[_outbox(event_id, tx=tx)],
        expected={stream_id: 0},
    )


@pytest.mark.parametrize('source', ['new', 'json', 'delete'])
def test_wal_is_ready_before_concurrent_writers_open_their_connections(tmp_path, source):
    path = tmp_path / 'ledger.db'
    if source == 'json':
        original = GameplayEventStore()
        assert original.append_batch(_batch()).committed
        original.save_snapshot(path)
    elif source == 'delete':
        DurableGameplayEventStore(path).close()
        with closing(sqlite3.connect(path)) as connection:
            assert connection.execute('PRAGMA journal_mode=DELETE').fetchone() == ('delete',)
    store = DurableGameplayEventStore(path)
    try:
        # 首次业务读写前完成模式切换，两个独立写者不再争夺这次迁移。
        with closing(sqlite3.connect(path)) as connection:
            assert connection.execute('PRAGMA journal_mode').fetchone() == ('wal',)
        assert store.get_last_global_sequence() == (2 if source == 'json' else 0)
        store.audit()
    finally:
        store.close()


def test_reused_connection_preserves_full_durability_and_cross_thread_reads(tmp_path, monkeypatch):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    original_connect = sqlite3.connect
    connections = []

    def connect(database, *args, **kwargs):
        result = original_connect(database, *args, **kwargs)
        if Path(database) == path:
            connections.append(result)
        return result

    monkeypatch.setattr(sqlite3, "connect", connect)
    try:
        assert store.get_last_global_sequence() == 0
        with ThreadPoolExecutor(max_workers=1) as pool:
            committed = pool.submit(store.append_batch, _batch()).result(timeout=5)
            assert committed.committed
            assert pool.submit(store.get_event, committed.committed_event_ids[0]).result(timeout=5).global_sequence == 1
        assert store.get_last_global_sequence() == 2
        assert len(connections) == 1
        assert connections[0].execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connections[0].execute("PRAGMA synchronous").fetchone() == (2,)
        assert not connections[0].in_transaction
    finally:
        if hasattr(store, "close"):
            store.close()


def test_group_commit_persists_independent_batches_with_one_sqlite_commit(tmp_path):
    path = tmp_path / "group-success.db"
    store = DurableGameplayEventStore(path)
    statements = []
    store._database_connection().set_trace_callback(statements.append)

    with store.group_commit():
        assert store.append_batch(_single_batch(suffix="first", stream_id="stream:group:first")).committed
        assert store.append_batch(_single_batch(suffix="second", stream_id="stream:group:second")).committed
        assert store.get_last_global_sequence() == 2

    assert sum(statement == "COMMIT" for statement in statements) == 1
    assert [event.event_id for event in DurableGameplayEventStore(path).read_events()] == [
        "evt:group:first",
        "evt:group:second",
    ]


def test_group_commit_rolls_back_all_batches_when_scope_raises(tmp_path):
    path = tmp_path / "group-rollback.db"
    store = DurableGameplayEventStore(path)

    with pytest.raises(RuntimeError, match="interrupt group"):
        with store.group_commit():
            assert store.append_batch(_single_batch(suffix="first", stream_id="stream:group:first")).committed
            raise RuntimeError("interrupt group")

    reopened = DurableGameplayEventStore(path)
    assert reopened.read_events() == []
    assert reopened.get_last_global_sequence() == 0


def test_group_commit_rolls_back_prior_batch_when_later_persistence_returns_failure(tmp_path, monkeypatch):
    path = tmp_path / "group-write-failure.db"
    store = DurableGameplayEventStore(path)
    original = store._write_delta
    def fail_write(**_kwargs):
        raise sqlite3.OperationalError("injected write failure")

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_group_commit_failed"):
        with store.group_commit():
            assert store.append_batch(_single_batch(suffix="first", stream_id="stream:group:first")).committed
            monkeypatch.setattr(store, "_write_delta", fail_write)
            failed = store.append_batch(_single_batch(suffix="second", stream_id="stream:group:second"))
            assert failed.failure.error_code == "durable_persistence_failed"

    monkeypatch.setattr(store, "_write_delta", original)
    reopened = DurableGameplayEventStore(path)
    assert reopened.read_events() == []
    assert reopened.get_last_global_sequence() == 0


def test_close_is_terminal_and_releases_the_database(tmp_path):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(_batch()).committed
    store.close()
    store.close()
    for command in (store.get_last_global_sequence, store.export_snapshot, store.audit):
        with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_closed"):
            command()
    renamed = path.with_name("closed.db")
    path.rename(renamed)
    reopened = DurableGameplayEventStore(renamed)
    try:
        assert reopened.get_last_global_sequence() == 2
    finally:
        reopened.close()


def test_committed_wal_survives_process_exit_without_close(tmp_path):
    path = tmp_path / "killed.db"
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(Path(__file__).resolve().parent),
                                                    str(Path(__file__).resolve().parents[1]))))
    code = """
import os,sys
from app.gameplay.event_store import DurableGameplayEventStore
from test_gameplay_event_store_contract import _batch
store=DurableGameplayEventStore(sys.argv[1])
assert store.append_batch(_batch()).committed
os._exit(7)
"""
    child = subprocess.run([sys.executable, "-c", code, str(path)], env=env,
                           capture_output=True, text=True, timeout=15)
    assert child.returncode == 7, child.stderr
    assert path.with_name(path.name + "-wal").stat().st_size > 0
    store = DurableGameplayEventStore(path)
    try:
        assert store.get_last_global_sequence() == 2
        assert store.get_by_idempotency("player:local", "idempotency:handoff:1").committed
        assert len(store.list_outbox(include_delivered=False)) == 2
        assert store.append_batch(_batch()).idempotency_status == "duplicate_replayed"
        store.audit()
    finally:
        store.close()


def test_failed_close_is_terminal_and_retries_same_connection(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / 'close-failure.db')
    original_connect = sqlite3.connect
    class FailOnce(sqlite3.Connection):
        failed = False
        def close(self):
            if not self.failed:
                self.failed = True
                raise sqlite3.OperationalError('injected close failure')
            return super().close()
    monkeypatch.setattr(sqlite3, 'connect', lambda *args, **kwargs: original_connect(*args, **kwargs, factory=FailOnce))
    assert store.get_last_global_sequence() == 0
    original = store._connection
    with pytest.raises(sqlite3.OperationalError, match='injected close failure'): store.close()
    assert store._connection is original
    for operation in (store.get_last_global_sequence, store.export_snapshot, store.audit):
        with pytest.raises(GameplayEventStoreSnapshotError, match='gameplay_snapshot_closed'): operation()
        assert store._connection is original
    assert not store.append_batch(_batch()).committed
    assert store._connection is original
    assert original.execute('SELECT COUNT(*) FROM events').fetchone() == (0,)
    store.close()
    assert store._connection is None
    store.close()
