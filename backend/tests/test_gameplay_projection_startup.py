from __future__ import annotations

import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.projection_startup import GameplayProjectionStartup
from app.gameplay.replay import GameplayProjectionReplay

from test_gameplay_event_store_contract import _batch, _event, _outbox


def _append_counter_event(store: GameplayEventStore, number: int) -> None:
    event_id = f"evt:counter:{number}"
    transaction_id = f"tx:counter:{number}"
    command_id = f"cmd:counter:{number}"
    result = store.append_batch(
        _batch(
            tx=transaction_id,
            command_id=command_id,
            key=f"idempotency:counter:{number}",
            digest=f"digest:counter:{number}",
            events=[_event(event_id, stream_id="aggregate:counter", tx=transaction_id, command_id=command_id)],
            outbox_entries=[_outbox(event_id, tx=transaction_id)],
            expected={"aggregate:counter": number - 1},
        )
    )
    assert result.committed


def _replay() -> GameplayProjectionReplay:
    return GameplayProjectionReplay(projector_id="projection:counter", projector_version="v1")


def test_startup_selects_newest_compatible_checkpoint_and_replays_tail() -> None:
    store = GameplayEventStore()
    _append_counter_event(store, 1)
    _append_counter_event(store, 2)
    replay = _replay()
    old_checkpoint = replay.create_checkpoint(store.read_events()[:1])
    newest_checkpoint = replay.create_checkpoint(
        store.read_events()[:2],
        active_patch_set_revision="patch:7",
        registry_revision="registry:5",
        world_config_revision="world:3",
    )
    store.save_projection_checkpoint(old_checkpoint)
    store.save_projection_checkpoint(newest_checkpoint)

    result = GameplayProjectionStartup(
        store=store,
        replay=replay,
        active_patch_set_revision="patch:7",
        registry_revision="registry:5",
        world_config_revision="world:3",
    ).bootstrap()

    assert result.read_ready is True
    assert result.write_ready is True
    assert result.selected_checkpoint_id == newest_checkpoint.checkpoint_id
    assert result.replay_result.projection_hash == replay.full_replay(store.read_events()).projection_hash
    assert store.write_ready is True


def test_startup_ignores_invalid_or_incompatible_checkpoints_and_full_replays() -> None:
    store = GameplayEventStore()
    _append_counter_event(store, 1)
    _append_counter_event(store, 2)
    replay = _replay()
    checksum_invalid = replay.create_checkpoint(store.read_events()[:1]).model_copy(
        update={"checkpoint_id": "checkpoint:invalid", "state": {"tampered": True}},
        deep=True,
    )
    incompatible = replay.create_checkpoint(
        store.read_events(),
        active_patch_set_revision="patch:old",
        registry_revision="registry:5",
        world_config_revision="world:3",
    )
    store.save_projection_checkpoint(checksum_invalid)
    store.save_projection_checkpoint(incompatible)

    result = GameplayProjectionStartup(
        store=store,
        replay=replay,
        active_patch_set_revision="patch:current",
        registry_revision="registry:5",
        world_config_revision="world:3",
    ).bootstrap()

    assert result.read_ready is True
    assert result.write_ready is True
    assert result.selected_checkpoint_id is None
    assert result.replay_result.applied_event_count == 2


def test_projection_checkpoint_snapshot_round_trip_preserves_compatibility_metadata(tmp_path) -> None:
    store = GameplayEventStore()
    _append_counter_event(store, 1)
    checkpoint = _replay().create_checkpoint(
        store.read_events(),
        active_patch_set_revision="patch:7",
        registry_revision="registry:5",
        world_config_revision="world:3",
    )
    store.save_projection_checkpoint(checkpoint)
    path = tmp_path / "gameplay-store.json"
    store.save_snapshot(path)

    restored = GameplayEventStore.load_snapshot(path)

    assert restored.list_projection_checkpoints() == [checkpoint]


def test_failed_startup_keeps_writes_closed_and_returns_typed_rejection() -> None:
    store = GameplayEventStore()
    _append_counter_event(store, 1)
    corrupt_event = store.read_events()[0].model_copy(update={"stream_revision": 2}, deep=True)
    store._events = [corrupt_event]
    store._events_by_id = {corrupt_event.event_id: corrupt_event}

    result = GameplayProjectionStartup(store=store, replay=_replay()).bootstrap()
    rejected = store.append_batch(
        _batch(
            tx="tx:after-failure",
            command_id="cmd:after-failure",
            key="idempotency:after-failure",
            digest="digest:after-failure",
            events=[_event("evt:after-failure", stream_id="aggregate:after-failure", tx="tx:after-failure", command_id="cmd:after-failure")],
            outbox_entries=[_outbox("evt:after-failure", tx="tx:after-failure")],
            expected={"aggregate:after-failure": 0},
        )
    )

    assert result.read_ready is False
    assert result.write_ready is False
    assert result.failure is not None and result.failure.error_code == "stream_revision_gap"
    assert store.write_ready is False
    assert rejected.committed is False
    assert rejected.failure is not None
    assert rejected.failure.error_code == "projection_not_ready"
    assert rejected.failure.retriable is True


def test_successful_startup_opens_writes() -> None:
    store = GameplayEventStore()
    _append_counter_event(store, 1)

    result = GameplayProjectionStartup(store=store, replay=_replay()).bootstrap()
    accepted = store.append_batch(
        _batch(
            tx="tx:after-success",
            command_id="cmd:after-success",
            key="idempotency:after-success",
            digest="digest:after-success",
            events=[_event("evt:after-success", stream_id="aggregate:after-success", tx="tx:after-success", command_id="cmd:after-success")],
            outbox_entries=[_outbox("evt:after-success", tx="tx:after-success")],
            expected={"aggregate:after-success": 0},
        )
    )

    assert result.read_ready is True
    assert result.write_ready is True
    assert store.write_ready is True
    assert accepted.committed is True


@pytest.mark.parametrize("field", ["registry_revision", "world_config_revision"])
def test_startup_rejects_checkpoint_with_incompatible_revision_dimension(field: str) -> None:
    store = GameplayEventStore()
    _append_counter_event(store, 1)
    replay = _replay()
    checkpoint = replay.create_checkpoint(
        store.read_events(),
        active_patch_set_revision="patch:7",
        registry_revision="registry:old",
        world_config_revision="world:old",
    )
    store.save_projection_checkpoint(checkpoint)
    expected = {
        "active_patch_set_revision": "patch:7",
        "registry_revision": "registry:old",
        "world_config_revision": "world:old",
    }
    expected[field] = "registry:current" if field == "registry_revision" else "world:current"

    result = GameplayProjectionStartup(store=store, replay=replay, **expected).bootstrap()

    assert result.selected_checkpoint_id is None
    assert result.replay_result.succeeded is True
