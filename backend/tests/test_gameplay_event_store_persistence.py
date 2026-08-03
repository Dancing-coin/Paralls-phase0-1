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
