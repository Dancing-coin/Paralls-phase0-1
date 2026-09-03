from __future__ import annotations

from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayEvent
from app.gameplay.replay import GameplayProjectionReplay


def _run_three_period_bakery() -> tuple[GameplayEventStore, list[GameplayEvent], list[int]]:
    store = GameplayEventStore()
    BakeryReferenceScenario.default().run_three_periods(store=store)
    events = store.read_events()
    period_close_sequences = [
        event.global_sequence
        for event in events
        if event.event_type == "gameplay.economy.business_period_closed"
    ]
    return store, events, period_close_sequences


def _stored_checkpoint(store: GameplayEventStore, checkpoint_id: str):
    return next(
        checkpoint
        for checkpoint in store.list_projection_checkpoints(projector_id="bakery-loop-v1")
        if checkpoint.checkpoint_id == checkpoint_id
    )


def test_bakery_full_and_checkpoint_tail_replay_match_across_three_periods() -> None:
    store, events, period_close_sequences = _run_three_period_bakery()
    replay = GameplayProjectionReplay(projector_id="bakery-loop-v1", projector_version="1")
    full = replay.full_replay(events)

    assert full.succeeded is True
    assert period_close_sequences == sorted(period_close_sequences)
    assert len(period_close_sequences) == 3

    for split_at in period_close_sequences:
        checkpoint = replay.create_checkpoint(events[:split_at])
        store.save_projection_checkpoint(checkpoint)
        stored = _stored_checkpoint(store, checkpoint.checkpoint_id)
        tail = replay.checkpoint_plus_tail_replay(stored, events[split_at:])

        assert tail.succeeded is True
        assert tail.projection_hash == full.projection_hash
        assert tail.state == full.state
        assert tail.source_revision_vector == full.source_revision_vector
        assert tail.applied_event_ids == full.applied_event_ids


def test_bakery_tampered_checkpoint_is_rejected() -> None:
    _, events, period_close_sequences = _run_three_period_bakery()
    replay = GameplayProjectionReplay(projector_id="bakery-loop-v1", projector_version="1")
    checkpoint = replay.create_checkpoint(events[: period_close_sequences[1]])
    tampered = checkpoint.model_copy(update={"projection_hash": "sha256:tampered"}, deep=True)

    assert replay.select_compatible_checkpoint([tampered], events) is None

    result = replay.checkpoint_plus_tail_replay(tampered, events[period_close_sequences[1] :])

    assert result.succeeded is False
    assert result.failure is not None
    assert result.failure.error_code == "checkpoint_invalid"
