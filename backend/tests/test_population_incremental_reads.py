from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore

from test_gameplay_event_store_contract import _batch, _event, _outbox


def test_event_store_indexes_stream_and_transaction_tails() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            tx="tx:index:first",
            command_id="cmd:index:first",
            key="key:index:first",
            events=[
                _event("evt:index:1", stream_id="stream:index", tx="tx:index:first", command_id="cmd:index:first"),
                _event("evt:index:2", stream_id="stream:index", tx="tx:index:first", command_id="cmd:index:first"),
            ],
            outbox_entries=[
                _outbox("evt:index:1", tx="tx:index:first"),
                _outbox("evt:index:2", tx="tx:index:first"),
            ],
            expected={"stream:index": 0},
        )
    )
    store.append_batch(
        _batch(
            tx="tx:index:second",
            command_id="cmd:index:second",
            key="key:index:second",
            events=[
                _event("evt:index:3", stream_id="stream:index", tx="tx:index:second", command_id="cmd:index:second"),
            ],
            outbox_entries=[_outbox("evt:index:3", tx="tx:index:second")],
            expected={"stream:index": 2},
        )
    )

    assert [event.event_id for event in store.read_stream("stream:index", from_revision=2)] == [
        "evt:index:2",
        "evt:index:3",
    ]
    assert [event.event_id for event in store.read_events(global_sequence_after=2)] == ["evt:index:3"]
    assert [batch.transaction_id for batch in store.read_transactions(global_position=2)] == [
        "tx:index:first",
        "tx:index:second",
    ]
    assert [event.event_id for event in store._events_by_stream["stream:index"]] == [
        "evt:index:1",
        "evt:index:2",
        "evt:index:3",
    ]
    assert store._transaction_end_sequences == [2, 3]


def test_event_store_rebuilds_incremental_indexes_from_snapshot() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:index:restore", stream_id="stream:index:restore")],
            outbox_entries=[_outbox("evt:index:restore")],
            expected={"stream:index:restore": 0},
        )
    )

    restored = GameplayEventStore.from_snapshot(store.export_snapshot())

    assert [event.event_id for event in restored.read_stream("stream:index:restore")] == ["evt:index:restore"]
    assert restored._transaction_end_sequences == [1]
