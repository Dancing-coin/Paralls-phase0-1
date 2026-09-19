"""连接复用不得改变原事务可见性、崩溃恢复和资源关闭边界。"""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStoreSnapshotError
from test_gameplay_event_store_contract import _batch


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
