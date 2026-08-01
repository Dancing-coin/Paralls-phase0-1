from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay

from test_gameplay_event_store_contract import _batch, _event, _outbox


def test_full_replay_and_checkpoint_plus_tail_replay_have_identical_projection_hashes() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:counter:1", stream_id="aggregate:counter")],
            outbox_entries=[_outbox("evt:counter:1")],
            expected={"aggregate:counter": 0},
        )
    )
    store.append_batch(
        _batch(
            tx="tx:gameplay:2",
            command_id="cmd:gameplay:2",
            key="idempotency:counter:2",
            digest="digest:v2",
            events=[_event("evt:counter:2", stream_id="aggregate:counter", tx="tx:gameplay:2", command_id="cmd:gameplay:2")],
            outbox_entries=[_outbox("evt:counter:2", tx="tx:gameplay:2")],
            expected={"aggregate:counter": 1},
        )
    )
    replay = GameplayProjectionReplay(projector_id="projection:counter", projector_version="v1")
    events = store.read_events()

    full = replay.full_replay(events)
    checkpoint = replay.create_checkpoint(events[:1])
    checkpointed = replay.checkpoint_plus_tail_replay(checkpoint, events[1:])

    assert full.succeeded is True
    assert checkpointed.succeeded is True
    assert full.projection_hash == checkpointed.projection_hash
    assert full.source_revision_vector == {"aggregate:counter": 2}


def test_replay_is_idempotent_for_duplicate_event_delivery() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:counter:1", stream_id="aggregate:counter")],
            outbox_entries=[_outbox("evt:counter:1")],
            expected={"aggregate:counter": 0},
        )
    )
    replay = GameplayProjectionReplay(projector_id="projection:counter", projector_version="v1")
    event = store.read_events()[0]

    result = replay.full_replay([event, event])

    assert result.succeeded is True
    assert result.applied_event_count == 1
    assert result.source_revision_vector == {"aggregate:counter": 1}


def test_stream_revision_gap_blocks_replay_with_typed_failure() -> None:
    store = GameplayEventStore()
    store.append_batch(
        _batch(
            events=[_event("evt:counter:1", stream_id="aggregate:counter")],
            outbox_entries=[_outbox("evt:counter:1")],
            expected={"aggregate:counter": 0},
        )
    )
    event = store.read_events()[0].model_copy(update={"stream_revision": 3})
    replay = GameplayProjectionReplay(projector_id="projection:counter", projector_version="v1")

    result = replay.full_replay([event])

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "stream_revision_gap"


def test_unknown_event_version_blocks_replay_with_upcast_failure() -> None:
    store = GameplayEventStore()
    event = _event("evt:counter:v2", stream_id="aggregate:counter")
    event["schema_version"] = 2
    store.append_batch(
        _batch(
            events=[event],
            outbox_entries=[_outbox("evt:counter:v2")],
            expected={"aggregate:counter": 0},
        )
    )
    replay = GameplayProjectionReplay(
        projector_id="projection:counter",
        projector_version="v1",
        supported_event_versions={"gameplay.session_reserved": 1},
    )

    result = replay.full_replay(store.read_events())

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "upcaster_chain_missing"
