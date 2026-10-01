from contextlib import closing
import sqlite3

import pytest

from app.gameplay.event_store import DurableGameplayEventStore
from test_gameplay_event_store_contract import _batch
from test_gameplay_event_store_lazy_restore import schema_one_database


def _identity_indexes(connection):
    indexes = []
    for name, unique in connection.execute(
        'SELECT name, "unique" FROM pragma_index_list(?)', ("transactions",)
    ):
        columns = connection.execute(
            "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (name,)
        ).fetchall()
        if unique and columns == [("transaction_id",)]:
            indexes.append(name)
    return sorted(indexes)


def test_new_database_maintains_one_transaction_identity_index(tmp_path):
    path = tmp_path / "fresh.db"
    store = DurableGameplayEventStore(path)
    try:
        with closing(sqlite3.connect(path)) as connection:
            assert _identity_indexes(connection) == ["transactions_identity"]
    finally:
        store.close()


@pytest.mark.parametrize("legacy", [False, True])
def test_native_duplicate_identity_rolls_back_without_ledger_changes(tmp_path, legacy):
    path = tmp_path / "identity.db"
    if legacy:
        schema_one_database(path)
    store = DurableGameplayEventStore(path)
    try:
        if not legacy:
            assert store.append_batch(_batch()).committed
        snapshot = store.export_snapshot()
        with closing(sqlite3.connect(path)) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="transactions.transaction_id"):
                with connection:
                    connection.execute("INSERT INTO metadata VALUES ('probe', 'rollback')")
                    connection.execute(
                        "INSERT INTO transactions "
                        "SELECT sequence+1000, batch, result, transaction_id, "
                        "principal_ref||':other', idempotency_key||':other', "
                        "payload_digest, refresh_state FROM transactions LIMIT 1"
                    )
            assert connection.execute(
                "SELECT COUNT(*) FROM metadata WHERE key='probe'"
            ).fetchone() == (0,)
            assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone() == (1,)
        assert store.export_snapshot() == snapshot
        store.audit()
    finally:
        store.close()


def test_new_database_rejects_native_null_transaction_identity(tmp_path):
    path = tmp_path / "not-null.db"
    store = DurableGameplayEventStore(path)
    try:
        assert store.append_batch(_batch()).committed
        with closing(sqlite3.connect(path)) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="NOT NULL"):
                with connection:
                    connection.execute(
                        "INSERT INTO transactions "
                        "SELECT sequence+1000, batch, result, NULL, "
                        "principal_ref||':other', idempotency_key||':other', "
                        "payload_digest, refresh_state FROM transactions LIMIT 1"
                    )
            assert connection.execute("SELECT COUNT(*) FROM transactions").fetchone() == (1,)
        store.audit()
    finally:
        store.close()


def test_legacy_double_index_database_reopens_without_rebuilding(tmp_path, monkeypatch):
    path = tmp_path / "legacy-double-index.db"
    old_schema = tuple(
        statement.replace("transaction_id TEXT NOT NULL,", "transaction_id TEXT NOT NULL UNIQUE,")
        if statement.startswith("CREATE TABLE IF NOT EXISTS transactions ") else statement
        for statement in DurableGameplayEventStore._SCHEMA
    )
    with monkeypatch.context() as patch:
        patch.setattr(DurableGameplayEventStore, "_SCHEMA", old_schema)
        original = DurableGameplayEventStore(path)
        try:
            assert original.append_batch(_batch()).committed
            snapshot = original.export_snapshot()
        finally:
            original.close()
    with closing(sqlite3.connect(path)) as connection:
        old_indexes = _identity_indexes(connection)
        assert len(old_indexes) == 2
        old_version = connection.execute("PRAGMA schema_version").fetchone()
        old_table = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
        ).fetchone()
    restored = DurableGameplayEventStore(path)
    try:
        assert restored.export_snapshot() == snapshot
        assert restored.append_batch(_batch()).idempotency_status == "duplicate_replayed"
        restored.audit()
        with closing(sqlite3.connect(path)) as connection:
            assert _identity_indexes(connection) == old_indexes
            assert connection.execute("PRAGMA schema_version").fetchone() == old_version
            assert connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='transactions'"
            ).fetchone() == old_table
    finally:
        restored.close()
