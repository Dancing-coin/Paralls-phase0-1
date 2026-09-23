import sqlite3
from time import monotonic, sleep

import pytest

from app.services.sqlite_wal_checkpoint import start_sqlite_wal_checkpoint_worker


def test_background_checkpoint_moves_wal_work_off_writer_and_stops_cleanly(tmp_path):
    if sqlite3.sqlite_version_info < (3, 51, 3):
        pytest.skip("concurrent WAL checkpoint requires SQLite 3.51.3+")
    path = tmp_path / "runtime.sqlite3"
    writer = sqlite3.connect(path)
    assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    writer.execute("PRAGMA synchronous=FULL")
    writer.execute("CREATE TABLE events (sequence INTEGER PRIMARY KEY, payload BLOB NOT NULL)")
    worker = start_sqlite_wal_checkpoint_worker(((path, writer),), interval_seconds=.01)
    assert worker is not None
    try:
        assert writer.execute("PRAGMA wal_autocheckpoint").fetchone() == (0,)
        for sequence in range(1, 81):
            with writer:
                writer.execute("INSERT INTO events VALUES (?, ?)", (sequence, b"x" * 8192))
            sleep(.002)
        deadline = monotonic() + 2
        while worker.snapshot()["completed"] == 0 and monotonic() < deadline:
            sleep(.01)
        snapshot = worker.snapshot()
        assert snapshot["database_count"] == 1
        assert snapshot["completed"] > 0
        assert snapshot["failure"] is None
        worker.close()
        assert writer.execute("PRAGMA wal_autocheckpoint").fetchone() == (1000,)
    finally:
        if worker.is_alive():
            worker.close()
        writer.close()
    assert not worker.is_alive()


def test_older_sqlite_keeps_connection_local_autocheckpoint(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite3"
    writer = sqlite3.connect(path)
    assert writer.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    writer.execute("PRAGMA wal_autocheckpoint=777")
    monkeypatch.setattr(sqlite3, "sqlite_version_info", (3, 50, 6))
    try:
        assert start_sqlite_wal_checkpoint_worker(((path, writer),), interval_seconds=.01) is None
        assert writer.execute("PRAGMA wal_autocheckpoint").fetchone() == (777,)
    finally:
        writer.close()
