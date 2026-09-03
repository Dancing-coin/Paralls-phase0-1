from __future__ import annotations

from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay


def test_full_and_checkpoint_tail_replay_match_bakery_events_and_mirror() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.run_three_periods(store=store)
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="bakery-loop", projector_version="1")
    full = replay.full_replay(events)
    checkpoint_at = len(events) // 2
    checkpoint = replay.create_checkpoint(events[:checkpoint_at])
    tail = replay.checkpoint_plus_tail_replay(checkpoint, events[checkpoint_at:])
    assert full.succeeded and tail.succeeded
    assert full.projection_hash == tail.projection_hash
    assert full.source_revision_vector == tail.source_revision_vector
    assert full.applied_event_ids == tail.applied_event_ids
    assert BakeryMirrorSource(scenario=scenario, events=events).godot_view().view_checksum


def test_tampered_checkpoint_is_rejected() -> None:
    scenario = BakeryReferenceScenario.default()
    store = GameplayEventStore()
    scenario.run_three_periods(store=store)
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="bakery-loop", projector_version="1")
    checkpoint = replay.create_checkpoint(events[: len(events) // 2])
    tampered = checkpoint.model_copy(update={"state": {"tampered": True}})
    result = replay.checkpoint_plus_tail_replay(tampered, events[len(events) // 2 :])
    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.error_code == "checkpoint_invalid"
