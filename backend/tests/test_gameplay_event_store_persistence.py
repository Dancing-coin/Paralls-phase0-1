from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore, GameplayEventStoreSnapshotError

from test_gameplay_event_store_contract import _batch, _event, _outbox


def test_snapshot_round_trip_recovers_events_idempotency_and_outbox_state(tmp_path) -> None:
    path = tmp_path / "gameplay-store.json"
    store = GameplayEventStore()
    committed = store.append_batch(
        _batch(
            events=[_event("evt:persisted", stream_id="stream:persisted")],
            outbox_entries=[_outbox("evt:persisted")],
            expected={"stream:persisted": 0},
        )
    )
    store.mark_outbox_delivered("outbox:evt:persisted")
    store.save_snapshot(path)

    restored = GameplayEventStore.load_snapshot(path)
    assert [event.event_id for event in restored.read_events()] == ["evt:persisted"]
    assert restored.get_stream_head("stream:persisted") == 1
    assert restored.list_outbox()[0].delivery_state == "delivered"
    replay = restored.append_batch(
        _batch(
            tx="tx:duplicate",
            events=[_event("evt:duplicate", stream_id="stream:other", tx="tx:duplicate")],
            outbox_entries=[_outbox("evt:duplicate", tx="tx:duplicate")],
            expected={"stream:other": 0},
        )
    )
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.transaction_id == committed.transaction_id
    assert [event.event_id for event in restored.read_events()] == ["evt:persisted"]


def test_snapshot_load_fails_closed_for_corrupt_or_unsupported_data(tmp_path) -> None:
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_load_failed"):
        GameplayEventStore.load_snapshot(corrupt)

    unsupported = tmp_path / "unsupported.json"
    unsupported.write_text(json.dumps({"snapshot_schema_version": 99}), encoding="utf-8")
    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_schema_unsupported"):
        GameplayEventStore.load_snapshot(unsupported)


def test_snapshot_load_rejects_transaction_result_that_does_not_match_committed_batch() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:integrity", stream_id="stream:integrity")],
            outbox_entries=[_outbox("evt:integrity")],
            expected={"stream:integrity": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["transaction_results"][0]["committed_event_ids"] = ["evt:forged"]

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_result_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_outbox_entry_bound_to_the_wrong_transaction() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:outbox-integrity", stream_id="stream:outbox-integrity")],
            outbox_entries=[_outbox("evt:outbox-integrity")],
            expected={"stream:outbox-integrity": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["outbox"][0]["transaction_id"] = "tx:forged"

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_outbox_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_transaction_event_payload_that_differs_from_ledger_event() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:event-integrity", stream_id="stream:event-integrity")],
            outbox_entries=[_outbox("evt:event-integrity")],
            expected={"stream:event-integrity": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["transactions"][0]["events"][0]["payload"]["slot"] = "tampered"

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_batch_idempotency_record_that_differs_from_index() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:idempotency-integrity", stream_id="stream:idempotency-integrity")],
            outbox_entries=[_outbox("evt:idempotency-integrity")],
            expected={"stream:idempotency-integrity": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["transactions"][0]["idempotency_record"]["payload_digest"] = "digest:forged"

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_batch_expected_revision_that_does_not_precede_committed_events() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:revision-integrity", stream_id="stream:revision-integrity")],
            outbox_entries=[_outbox("evt:revision-integrity")],
            expected={"stream:revision-integrity": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["transactions"][0]["expected_stream_revisions"]["stream:revision-integrity"] = 7

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_missing_transaction_outbox_entry() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:outbox-coverage", stream_id="stream:outbox-coverage")],
            outbox_entries=[_outbox("evt:outbox-coverage")],
            expected={"stream:outbox-coverage": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["transactions"][0]["outbox_entries"] = []

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_transactions_out_of_global_sequence_order() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            tx="tx:sequence:first",
            command_id="cmd:sequence:first",
            key="key:sequence:first",
            events=[_event("evt:sequence:first", stream_id="stream:sequence:first", tx="tx:sequence:first", command_id="cmd:sequence:first")],
            outbox_entries=[_outbox("evt:sequence:first", tx="tx:sequence:first")],
            expected={"stream:sequence:first": 0},
        )
    )
    store.append_batch(
        _batch(
            tx="tx:sequence:second",
            command_id="cmd:sequence:second",
            key="key:sequence:second",
            events=[_event("evt:sequence:second", stream_id="stream:sequence:second", tx="tx:sequence:second", command_id="cmd:sequence:second")],
            outbox_entries=[_outbox("evt:sequence:second", tx="tx:sequence:second")],
            expected={"stream:sequence:second": 0},
        )
    )
    snapshot = store.export_snapshot()
    snapshot["transactions"].reverse()

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_snapshot_load_rejects_non_contiguous_event_sequences_inside_a_batch() -> None:
    store = GameplayEventStore()
    store.append_batch(_batch())
    snapshot = store.export_snapshot()
    snapshot["transactions"][0]["events"].reverse()

    with pytest.raises(GameplayEventStoreSnapshotError, match="gameplay_snapshot_transaction_invalid"):
        GameplayEventStore.from_snapshot(snapshot)


def test_durable_store_persists_commit_and_rolls_back_when_snapshot_write_fails(tmp_path, monkeypatch) -> None:
    path = tmp_path / "durable-store.json"
    store = DurableGameplayEventStore(path)
    committed = store.append_batch(_batch(events=[_event("evt:durable", stream_id="stream:durable")], outbox_entries=[_outbox("evt:durable")], expected={"stream:durable": 0}))
    assert committed.committed
    assert DurableGameplayEventStore(path).read_events()[0].event_id == "evt:durable"

    monkeypatch.setattr(store, "_write_delta", lambda *args, **kwargs: (_ for _ in ()).throw(GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed")))
    failed = store.append_batch(_batch(tx="tx:failed", command_id="cmd:failed", key="key:failed", digest="digest:failed", events=[_event("evt:failed", stream_id="stream:failed", tx="tx:failed", command_id="cmd:failed")], outbox_entries=[_outbox("evt:failed", tx="tx:failed")], expected={"stream:failed": 0}))
    assert not failed.committed
    assert failed.failure is not None and failed.failure.error_code == "durable_persistence_failed"
    assert [event.event_id for event in store.read_events()] == ["evt:durable"]


def test_durable_updates_never_copy_history_and_legacy_snapshot_migrates(tmp_path, monkeypatch):
    from app.gameplay.models import ProjectionCheckpoint

    path = tmp_path / "legacy.json"
    legacy = GameplayEventStore()
    legacy.append_batch(_batch())
    legacy.save_snapshot(path)
    store = DurableGameplayEventStore(path)
    monkeypatch.setattr(store, "export_snapshot", lambda: pytest.fail("hot path copied history"))
    monkeypatch.setattr(store, "save_snapshot", lambda *_: pytest.fail("hot path rewrote history"))
    store.mark_outbox_delivered("outbox:evt:session:reserved")
    checkpoint = ProjectionCheckpoint(checkpoint_id="cp:1", projector_id="population", projector_version="2",
        projection_schema_version=2, last_global_sequence=2, projection_hash="sha256:test", state={"tail": 2})
    store.save_projection_checkpoint(checkpoint)
    batch = _batch(tx="tx:tail", command_id="cmd:tail", key="key:tail", digest="digest:tail",
        events=[_event("evt:tail", stream_id="tail", tx="tx:tail", command_id="cmd:tail")],
        outbox_entries=[_outbox("evt:tail", tx="tx:tail")], expected={"tail": 0})
    assert store.append_batch(batch).committed
    assert store.append_batch(batch).idempotency_status == "duplicate_replayed"
    restored = DurableGameplayEventStore(path)
    assert restored.get_last_global_sequence() == 3
    assert restored.get_projection_checkpoint("cp:1") == checkpoint
    assert restored.list_outbox()[0].delivery_state == "delivered"
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM transactions").fetchone()[0] == 2


def test_durable_sql_failure_rolls_back_disk_memory_and_projection_updates(tmp_path, monkeypatch):
    from app.gameplay.models import ProjectionCheckpoint

    path = tmp_path / "store.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(_batch()).committed
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER reject_outbox BEFORE UPDATE ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END")
        connection.execute("CREATE TRIGGER reject_checkpoint BEFORE INSERT ON checkpoints BEGIN SELECT RAISE(ABORT, 'injected'); END")
    with pytest.raises(GameplayEventStoreSnapshotError):
        store.mark_outbox_delivered("outbox:evt:session:reserved")
    checkpoint = ProjectionCheckpoint(checkpoint_id="cp", projector_id="population", projector_version="2",
        projection_schema_version=2, projection_hash="sha256:test")
    with pytest.raises(GameplayEventStoreSnapshotError):
        store.save_projection_checkpoint(checkpoint)
    assert store.get_projection_checkpoint("cp") is None
    assert store.list_outbox()[0].delivery_state == "pending"
    assert DurableGameplayEventStore(path).export_snapshot() == store.export_snapshot()


def test_sql_failure_after_transaction_insert_rolls_back_all_indexes(tmp_path):
    path = tmp_path / "rollback.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(_batch()).committed
    before = store.export_snapshot()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TRIGGER reject_new_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'injected'); END")
    batch = _batch(tx="tx:failed", command_id="cmd:failed", key="key:failed", digest="digest:failed",
        events=[_event("evt:failed", stream_id="body:char_a", tx="tx:failed", command_id="cmd:failed")],
        outbox_entries=[_outbox("evt:failed", tx="tx:failed")], expected={"body:char_a": 1})
    assert store.append_batch(batch).failure.error_code == "durable_persistence_failed"
    assert store.export_snapshot() == before
    assert DurableGameplayEventStore(path).export_snapshot() == before
    assert store.get_by_idempotency("player:local", "key:failed") is None
    with sqlite3.connect(path) as connection:
        connection.execute("DROP TRIGGER reject_new_outbox")
    assert store.append_batch(batch).committed
    assert store.read_stream("body:char_a")[-1].stream_revision == 2
    assert len(store.list_outbox(include_delivered=False)) == 3


def test_concurrent_failed_and_successful_durable_writers_do_not_undo_each_other(
    tmp_path, monkeypatch
):
    path = tmp_path / "concurrent-writers.db"
    store = DurableGameplayEventStore(path)
    original_write_delta = store._write_delta
    first_writer_waiting = threading.Event()
    second_writer_started = threading.Event()
    second_writer_in_delta = threading.Event()
    second_writer_persisted = threading.Event()
    results = {}

    def controlled_write_delta(*, batch=None, result=None, **kwargs):
        if batch is not None and batch.transaction_id == "tx:first":
            first_writer_waiting.set()
            assert second_writer_started.wait(5)
            if second_writer_in_delta.wait(0.5):
                assert second_writer_persisted.wait(5)
            raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed")
        if batch is not None and batch.transaction_id == "tx:second":
            second_writer_in_delta.set()
        original_write_delta(batch=batch, result=result, **kwargs)
        if batch is not None and batch.transaction_id == "tx:second":
            second_writer_persisted.set()

    monkeypatch.setattr(store, "_write_delta", controlled_write_delta)

    def append_first() -> None:
        results["first"] = store.append_batch(
            _batch(
                tx="tx:first",
                command_id="cmd:first",
                key="key:first",
                digest="digest:first",
                events=[
                    _event(
                        "evt:first",
                        stream_id="stream:first",
                        tx="tx:first",
                        command_id="cmd:first",
                    )
                ],
                outbox_entries=[_outbox("evt:first", tx="tx:first")],
                expected={"stream:first": 0},
            )
        )

    def append_second() -> None:
        assert first_writer_waiting.wait(5)
        second_writer_started.set()
        results["second"] = store.append_batch(
            _batch(
                tx="tx:second",
                command_id="cmd:second",
                key="key:second",
                digest="digest:second",
                events=[
                    _event(
                        "evt:second",
                        stream_id="stream:second",
                        tx="tx:second",
                        command_id="cmd:second",
                    )
                ],
                outbox_entries=[_outbox("evt:second", tx="tx:second")],
                expected={"stream:second": 0},
            )
        )

    first_thread = threading.Thread(target=append_first)
    second_thread = threading.Thread(target=append_second)
    first_thread.start()
    second_thread.start()
    first_thread.join(10)
    second_thread.join(10)

    assert not first_thread.is_alive()
    assert not second_thread.is_alive()
    assert not results["first"].committed
    assert results["first"].failure.error_code == "durable_persistence_failed"
    assert results["second"].committed
    assert [(event.event_id, event.global_sequence) for event in store.read_events()] == [
        ("evt:second", 1)
    ]
    assert [batch.transaction_id for batch in store.read_transactions()] == [
        "tx:second"
    ]

    reopened = DurableGameplayEventStore(path)
    assert reopened.export_snapshot() == store.export_snapshot()


def test_reader_cannot_observe_durable_event_before_failed_writer_rolls_back(
    tmp_path, monkeypatch
):
    store = DurableGameplayEventStore(tmp_path / "reader-writer.db")
    writer_in_delta = threading.Event()
    release_writer = threading.Event()
    reader_returned = threading.Event()
    observed_events = []
    writer_result = {}

    def fail_after_reader_starts(**_kwargs):
        writer_in_delta.set()
        assert release_writer.wait(5)
        raise GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed")

    monkeypatch.setattr(store, "_write_delta", fail_after_reader_starts)

    def append_event() -> None:
        writer_result["result"] = store.append_batch(
            _batch(
                events=[_event("evt:uncommitted", stream_id="stream:uncommitted")],
                outbox_entries=[_outbox("evt:uncommitted")],
                expected={"stream:uncommitted": 0},
            )
        )

    def read_events() -> None:
        assert writer_in_delta.wait(5)
        observed_events.extend(store.read_events())
        reader_returned.set()

    writer = threading.Thread(target=append_event)
    reader = threading.Thread(target=read_events)
    writer.start()
    reader.start()
    assert writer_in_delta.wait(5)
    reader_returned_before_rollback = reader_returned.wait(0.2)
    release_writer.set()
    writer.join(10)
    reader.join(10)

    assert not writer.is_alive()
    assert not reader.is_alive()
    assert not reader_returned_before_rollback
    assert observed_events == []
    assert not writer_result["result"].committed


def test_duplicate_transaction_id_cannot_commit_unrecoverable_history(tmp_path):
    path = tmp_path / "identity.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(_batch()).committed
    assert store.append_batch(_batch()).idempotency_status == "duplicate_replayed"
    result = store.append_batch(_batch(key="key:other", digest="digest:other",
        events=[_event("evt:other", stream_id="other")], outbox_entries=[_outbox("evt:other")], expected={"other": 0}))
    assert result.failure.error_code == "duplicate_transaction_id"
    assert DurableGameplayEventStore(path).export_snapshot() == store.export_snapshot()


def test_duplicate_event_id_inside_batch_is_rejected_before_durable_commit(tmp_path):
    path = tmp_path / "duplicate-event.db"
    store = DurableGameplayEventStore(path)
    payload = _batch(
        events=[
            _event("evt:duplicate-inside", stream_id="stream:a"),
            _event("evt:duplicate-inside", stream_id="stream:b"),
        ],
        expected={"stream:a": 0, "stream:b": 0},
    )
    payload["outbox_entries"] = []

    result = store.append_batch(payload)

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "duplicate_event_id"
    assert store.read_events() == []
    assert DurableGameplayEventStore(path).read_events() == []


def test_duplicate_outbox_id_inside_batch_is_rejected_before_durable_commit(tmp_path):
    path = tmp_path / "duplicate-outbox.db"
    store = DurableGameplayEventStore(path)
    payload = _batch(
        events=[_event("evt:outbox", stream_id="stream:outbox")],
        expected={"stream:outbox": 0},
    )
    payload["outbox_entries"] = [
        _outbox("evt:outbox"),
        _outbox("evt:outbox"),
    ]

    result = store.append_batch(payload)

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "duplicate_outbox_id"
    assert store.read_events() == []
    assert store.list_outbox() == []
    assert DurableGameplayEventStore(path).export_snapshot() == store.export_snapshot()


def test_snapshot_export_cannot_overwrite_live_database(tmp_path):
    path = tmp_path / "store.db"
    store = DurableGameplayEventStore(path)
    assert store.append_batch(_batch()).committed
    with pytest.raises(GameplayEventStoreSnapshotError, match="export_overwrites_database"):
        store.save_snapshot(path)
    export = tmp_path / "backup.json"
    store.save_snapshot(export)
    assert GameplayEventStore.load_snapshot(export).export_snapshot() == DurableGameplayEventStore(path).export_snapshot()


def test_registry_extension_commits_with_its_first_event(tmp_path):
    from app.gameplay.event_schema_registry import EventSchemaRegistry, EventSchemaRegistration

    registry = EventSchemaRegistry()
    registry.register(EventSchemaRegistration("gameplay.session_reserved", 1, "sha256:a"))
    path = tmp_path / "registry.db"
    store = DurableGameplayEventStore(path, event_schema_registry=registry)
    assert store.append_batch(_batch()).committed
    registry.register(EventSchemaRegistration("gameplay.new_kind", 1, "sha256:b"))
    event = _event("evt:new", stream_id="new", tx="tx:new", command_id="cmd:new")
    event["event_type"] = "gameplay.new_kind"
    batch = _batch(tx="tx:new", command_id="cmd:new", key="key:new", digest="digest:new",
        events=[event], outbox_entries=[_outbox("evt:new", tx="tx:new")], expected={"new": 0})
    with sqlite3.connect(path) as connection:
        before = connection.execute("SELECT value FROM metadata WHERE key='registry'").fetchone()[0]
        connection.execute("CREATE TRIGGER reject_append BEFORE INSERT ON transactions BEGIN SELECT RAISE(ABORT, 'injected'); END")
    assert not store.append_batch(batch).committed
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT value FROM metadata WHERE key='registry'").fetchone()[0] == before
        connection.execute("DROP TRIGGER reject_append")
    assert store.append_batch(batch).committed
    assert DurableGameplayEventStore(path).export_snapshot() == store.export_snapshot()
    assert DurableGameplayEventStore(path, event_schema_registry=registry).export_snapshot() == store.export_snapshot()
