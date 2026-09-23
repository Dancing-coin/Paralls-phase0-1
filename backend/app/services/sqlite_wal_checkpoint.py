from __future__ import annotations

from collections.abc import Iterable
import math
from pathlib import Path
import sqlite3
from threading import Event, Lock, Thread


class SqliteWalCheckpointError(RuntimeError):
    pass


class SqliteWalCheckpointWorker:
    """在独立线程执行 PASSIVE checkpoint，避免提交线程承担检查点 I/O。"""

    def __init__(
        self,
        paths: tuple[Path, ...],
        writer_settings: tuple[tuple[sqlite3.Connection, int], ...],
        *,
        interval_seconds: float,
    ) -> None:
        self._paths = paths
        self._writer_settings = writer_settings
        self._interval_seconds = interval_seconds
        self._stop = Event()
        self._lock = Lock()
        self._attempts = 0
        self._completed = 0
        self._busy = 0
        self._failure: BaseException | None = None
        self._thread = Thread(target=self._run, name="sqlite-wal-checkpoint", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        connections: list[sqlite3.Connection] = []
        try:
            for path in self._paths:
                connection = sqlite3.connect(path, timeout=0)
                connection.execute("PRAGMA busy_timeout=0")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("PRAGMA cache_size=-64")
                connection.execute("PRAGMA wal_autocheckpoint=0")
                connections.append(connection)
            while not self._stop.wait(self._interval_seconds):
                for connection in connections:
                    try:
                        busy, frames, checkpointed = connection.execute(
                            "PRAGMA wal_checkpoint(PASSIVE)"
                        ).fetchone()
                    except sqlite3.OperationalError as exc:
                        code = getattr(exc, "sqlite_errorcode", None)
                        if code is not None and code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                            with self._lock:
                                self._busy += 1
                            continue
                        raise
                    with self._lock:
                        self._attempts += 1
                        if busy:
                            self._busy += 1
                        elif frames == checkpointed:
                            self._completed += 1
        except BaseException as exc:
            with self._lock:
                self._failure = exc
            self._stop.set()
        finally:
            for connection in connections:
                connection.close()

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "database_count": len(self._paths),
                "attempts": self._attempts,
                "completed": self._completed,
                "busy": self._busy,
                "failure": type(self._failure).__name__ if self._failure is not None else None,
            }

    def failure(self) -> BaseException | None:
        with self._lock:
            return self._failure

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def close(self, *, timeout_seconds: float = 5.0) -> None:
        self._stop.set()
        self._thread.join(timeout_seconds)
        if self._thread.is_alive():
            raise SqliteWalCheckpointError("sqlite_wal_checkpoint_shutdown_timeout")
        for connection, pages in self._writer_settings:
            connection.execute(f"PRAGMA wal_autocheckpoint={pages}")
        failure = self.failure()
        if failure is not None:
            raise SqliteWalCheckpointError("sqlite_wal_checkpoint_failed") from failure


def start_sqlite_wal_checkpoint_worker(
    bindings: Iterable[tuple[str | Path, sqlite3.Connection]],
    *,
    interval_seconds: float = .25,
) -> SqliteWalCheckpointWorker | None:
    """旧 SQLite 保留连接内自动 checkpoint，避免并发 WAL reset 风险。"""
    if (type(interval_seconds) not in (int, float) or not math.isfinite(interval_seconds)
            or interval_seconds <= 0):
        raise ValueError("sqlite_wal_checkpoint_interval_invalid")
    rows = tuple((Path(path).resolve(), connection) for path, connection in bindings)
    if not rows:
        raise ValueError("sqlite_wal_checkpoint_bindings_required")
    if sqlite3.sqlite_version_info < (3, 51, 3):
        return None
    settings: list[tuple[sqlite3.Connection, int]] = []
    try:
        for path, connection in rows:
            if connection.execute("PRAGMA journal_mode").fetchone() != ("wal",):
                raise SqliteWalCheckpointError("sqlite_wal_checkpoint_requires_wal")
            previous = connection.execute("PRAGMA wal_autocheckpoint").fetchone()[0]
            settings.append((connection, previous))
            connection.execute("PRAGMA wal_autocheckpoint=0")
    except BaseException:
        for connection, pages in settings:
            connection.execute(f"PRAGMA wal_autocheckpoint={pages}")
        raise
    paths = tuple(dict.fromkeys(path for path, _ in rows))
    return SqliteWalCheckpointWorker(paths, tuple(settings), interval_seconds=interval_seconds)
