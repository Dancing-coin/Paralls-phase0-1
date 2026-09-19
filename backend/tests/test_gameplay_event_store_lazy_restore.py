from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore, GameplayEventStoreSnapshotError
from app.gameplay.models import ProjectionCheckpoint
from test_gameplay_event_store_contract import _batch, _event, _outbox


def history_batch(count):
    events = [_event(f"evt:{i}", stream_id="stream:history") for i in range(count)]
    return _batch(events=events, outbox_entries=[_outbox(str(event["event_id"])) for event in events], expected={"stream:history": 0})


@pytest.mark.parametrize("count", [1000, 10000])
def test_reopen_and_bounded_reads_do_not_materialize_history(tmp_path, monkeypatch, count):
    path = tmp_path / "ledger.db"
    original = DurableGameplayEventStore(path)
    assert original.append_batch(history_batch(count)).committed
    monkeypatch.setattr(GameplayEventStore, "from_snapshot", lambda *a, **kw: pytest.fail("normal reopen rebuilt history"))
    reads = []
    connect = sqlite3.connect
    class CountingCursor(sqlite3.Cursor):
        def fetchone(self):
            row = super().fetchone()
            if row is not None:
                reads.append(row)
            return row
        def __iter__(self):
            while (row := self.fetchone()) is not None:
                yield row
    class CountingConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            return self.cursor(factory=CountingCursor).execute(sql, parameters)
    monkeypatch.setattr(sqlite3, "connect", lambda *args, **kwargs: connect(*args, **kwargs, factory=CountingConnection))
    store = DurableGameplayEventStore(path)
    assert len(reads) == 4
    assert reads[3] == ("wal",)
    assert not store._events and not store._transactions and not store._outbox
    assert store.get_last_global_sequence() == count
    assert [event.global_sequence for event in store.read_stream("stream:history", from_revision=count-1, limit=1)] == [count-1]
    assert len(store.list_outbox(include_delivered=False, limit=1)) == 1
    assert store.get_event(f"evt:{count-1}").global_sequence == count
    assert store.get_by_idempotency("player:local", "idempotency:handoff:1").global_sequence_range == (1, count)
    # 装配与常驻连接各核验一次 WAL；实际元数据与五个查询行数不变。
    assert reads[4] == ("wal",)
    assert len(reads) == 10


@pytest.mark.parametrize("durable", [False, True])
def test_keyset_outbox_page_keeps_entries_sharing_one_event(tmp_path, durable):
    store = DurableGameplayEventStore(tmp_path / "ledger.db") if durable else GameplayEventStore()
    entry = _outbox("evt:one")
    batch = _batch(events=[_event("evt:one", stream_id="stream:one")],
        outbox_entries=[{**entry, "outbox_id": key} for key in ["z", "a", "m"]], expected={"stream:one": 0})
    assert store.append_batch(batch).committed
    cursor = None
    ids = []
    while page := store.list_outbox(include_delivered=False, topic="gameplay.committed", transaction_id="tx:gameplay:1", after_cursor=cursor, limit=1):
        row = page[0]
        ids.append(row.outbox_id)
        cursor = row.global_sequence, row.outbox_id
    assert ids == ["a", "m", "z"]
    assert store.list_outbox(topic="other", limit=1) == []
    tx = store.get_transaction("tx:gameplay:1")
    tx.events[0].payload["session_id"] = "mutated"
    assert store.get_transaction("tx:gameplay:1").events[0].payload["session_id"] == "session:handoff:1"
    assert store.get_transaction("missing") is None


def test_checkpoints_are_atomic_and_latest_query_is_bounded(tmp_path):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    def checkpoint(name, position):
        return ProjectionCheckpoint(checkpoint_id=name, projector_id="p", projector_version="1",
            projection_schema_version=1, last_global_sequence=position, projection_hash="hash", state={"position": position})
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER fail_second BEFORE INSERT ON checkpoints WHEN new.id='bad' BEGIN SELECT RAISE(FAIL, 'injected'); END")
    with pytest.raises(GameplayEventStoreSnapshotError):
        store.save_projection_checkpoints_atomic([checkpoint("good", 1), checkpoint("bad", 2)])
    assert store.list_projection_checkpoints() == []
    store.save_projection_checkpoints_atomic([checkpoint("one", 1), checkpoint("two", 2), checkpoint("three", 3)])
    assert [cp.checkpoint_id for cp in store.list_projection_checkpoints(projector_id="p", limit=2)] == ["three", "two"]


def test_independent_store_writers_recheck_revision_inside_sql_transaction(tmp_path):
    path = tmp_path / "ledger.db"
    left = DurableGameplayEventStore(path)
    right = DurableGameplayEventStore(path)
    def append(store, suffix):
        tx, cmd, event = f"tx:{suffix}", f"cmd:{suffix}", f"evt:{suffix}"
        return store.append_batch(_batch(tx=tx, command_id=cmd, key=suffix,
            events=[_event(event, stream_id="shared", tx=tx, command_id=cmd)],
            outbox_entries=[_outbox(event, tx=tx)], expected={"shared": 0}))
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(append, store, suffix) for store, suffix in [(left, "left"), (right, "right")]]
        results = [job.result(timeout=10) for job in jobs]
    assert sum(result.committed for result in results) == 1
    assert next(result for result in results if not result.committed).failure.error_code == "revision_conflict"
    assert left.get_last_global_sequence() == right.get_last_global_sequence() == 1


def test_audit_rejects_index_payload_drift(tmp_path):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(history_batch(2)).committed
    store.audit()
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE outbox SET topic='tampered' WHERE id='outbox:evt:0'")
    with pytest.raises(GameplayEventStoreSnapshotError):
        store.audit()


def schema_one_database(path):
    oracle = GameplayEventStore()
    result = oracle.append_batch(history_batch(3))
    oracle.mark_outbox_delivered("outbox:evt:0")
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE transactions (sequence INTEGER PRIMARY KEY, batch TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE outbox (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE checkpoints (id TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        connection.executemany("INSERT INTO metadata VALUES (?, ?)", [("schema", "1"), ("registry", "null")])
        connection.execute("INSERT INTO transactions VALUES (?, ?, ?)", (3, oracle.read_transactions()[0].model_dump_json(), result.model_dump_json()))
        connection.executemany("INSERT INTO outbox VALUES (?, ?)", [(entry.outbox_id, entry.model_dump_json()) for entry in oracle.list_outbox()])
    return oracle


def test_schema_one_migration_rolls_back_alter_and_can_retry(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    oracle = schema_one_database(path)
    connect = sqlite3.connect
    class InterruptedMigration(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "ALTER TABLE outbox ADD COLUMN topic TEXT":
                raise sqlite3.OperationalError("injected migration failure")
            return super().execute(sql, parameters)
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *args, **kwargs: connect(*args, **kwargs, factory=InterruptedMigration))
        with pytest.raises(GameplayEventStoreSnapshotError):
            DurableGameplayEventStore(path)
    with connect(path) as connection:
        assert connection.execute("SELECT value FROM metadata WHERE key='schema'").fetchone() == ("1",)
        assert [row[1] for row in connection.execute("PRAGMA table_info(transactions)")] == ["sequence", "batch", "result"]
    restored = DurableGameplayEventStore(path)
    assert restored.export_snapshot() == oracle.export_snapshot()
    assert restored.append_batch(history_batch(3)).idempotency_status == "duplicate_replayed"
    restored.audit()
    assert DurableGameplayEventStore(path).export_snapshot() == oracle.export_snapshot()


def test_commit_failure_leaves_no_rows_or_high_water(tmp_path, monkeypatch):
    path = tmp_path / "ledger.db"
    store = DurableGameplayEventStore(path)
    connect = sqlite3.connect
    class FailingCommit(sqlite3.Connection):
        def __exit__(self, exc_type, exc_value, traceback):
            if exc_type is None:
                self.rollback()
                raise sqlite3.OperationalError("injected commit failure")
            return super().__exit__(exc_type, exc_value, traceback)
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *args, **kwargs: connect(*args, **kwargs, factory=FailingCommit))
        result = store.append_batch(history_batch(2))
    assert result.failure.error_code == "durable_persistence_failed"
    assert store.get_last_global_sequence() == 0
    assert store.read_events() == []
    assert store.get_by_idempotency("player:local", "idempotency:handoff:1") is None
    assert store.append_batch(history_batch(2)).global_sequence_range == (1, 2)


def test_memory_and_sql_append_oracles_match_for_replay_conflict_and_multistream(tmp_path):
    memory, durable = GameplayEventStore(), DurableGameplayEventStore(tmp_path / "ledger.db")
    batches = [_batch(), _batch(), _batch(digest="different")]
    transaction = "tx:second"
    command = "cmd:second"
    batches.append(_batch(tx=transaction, command_id=command, key="key:second",
        events=[_event("evt:next:1", stream_id="body:char_a", tx=transaction, command_id=command),
                _event("evt:next:2", stream_id="body:char_a", tx=transaction, command_id=command)],
        expected={"body:char_a": 1}))
    for batch in batches:
        assert durable.append_batch(batch) == memory.append_batch(batch)
        assert durable.export_snapshot() == memory.export_snapshot()
    durable.audit()


@pytest.mark.parametrize("existing_schema_two", [False, True])
def test_topic_and_global_checkpoint_limit_use_indexes(tmp_path, existing_schema_two):
    path = tmp_path / "indexed.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(history_batch(1000)).committed
    if existing_schema_two:
        with sqlite3.connect(path) as connection:
            connection.execute("DROP INDEX IF EXISTS outbox_topic_sequence")
            connection.execute("DROP INDEX IF EXISTS checkpoints_sequence")
        store = DurableGameplayEventStore(path)
    statements = []
    connect = sqlite3.connect
    # 查询使用既有连接，追踪实际执行者而非后续新建连接。
    store._database_connection().set_trace_callback(statements.append)
    assert store.list_outbox(topic="absent", limit=1) == []
    assert store.list_projection_checkpoints(limit=1) == []
    queries = [sql for sql in statements if sql.startswith("SELECT value FROM")]
    assert len(queries) == 2
    with connect(path) as connection:
        for sql, index in zip(queries, ["outbox_topic_sequence", "checkpoints_sequence"]):
            plan = " ".join(row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + sql))
            assert index in plan
            assert "TEMP B-TREE" not in plan


def test_schema_two_index_upgrade_is_atomic_and_retryable(tmp_path, monkeypatch):
    path = tmp_path / "upgrade.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(history_batch(2)).committed
    before = store.export_snapshot()
    with sqlite3.connect(path) as connection:
        connection.execute("DROP INDEX IF EXISTS outbox_topic_sequence")
        connection.execute("DROP INDEX IF EXISTS checkpoints_sequence")
    connect = sqlite3.connect
    class InterruptedIndexUpgrade(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith("CREATE INDEX IF NOT EXISTS checkpoints_sequence "):
                raise sqlite3.OperationalError("injected index upgrade failure")
            return super().execute(sql, parameters)
    with monkeypatch.context() as patch:
        patch.setattr(sqlite3, "connect", lambda *args, **kwargs: connect(*args, **kwargs, factory=InterruptedIndexUpgrade))
        with pytest.raises(GameplayEventStoreSnapshotError):
            DurableGameplayEventStore(path)
    with connect(path) as connection:
        assert connection.execute("SELECT name FROM sqlite_master WHERE type='index' AND name IN ('outbox_topic_sequence','checkpoints_sequence')").fetchall() == []
    assert DurableGameplayEventStore(path).export_snapshot() == before
    assert DurableGameplayEventStore(path).export_snapshot() == before
