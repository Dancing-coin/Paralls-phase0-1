from __future__ import annotations

import json

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

    monkeypatch.setattr(store, "save_snapshot", lambda _path: (_ for _ in ()).throw(GameplayEventStoreSnapshotError("gameplay_snapshot_write_failed")))
    failed = store.append_batch(_batch(tx="tx:failed", command_id="cmd:failed", key="key:failed", digest="digest:failed", events=[_event("evt:failed", stream_id="stream:failed", tx="tx:failed", command_id="cmd:failed")], outbox_entries=[_outbox("evt:failed", tx="tx:failed")], expected={"stream:failed": 0}))
    assert not failed.committed
    assert failed.failure is not None and failed.failure.error_code == "durable_persistence_failed"
    assert [event.event_id for event in store.read_events()] == ["evt:durable"]
