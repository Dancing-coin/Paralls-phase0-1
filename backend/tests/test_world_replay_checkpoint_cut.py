from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from test_gameplay_event_store_contract import _batch


def test_consistent_cut_uses_existing_checkpoint_decoder_and_receipt_spine():
    from app.world_runtime.replay_checkpoint import capture_replay_cut

    store = GameplayEventStore()
    committed = store.append_batch(_batch())
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay,
                             expected_owner_revisions={"session:handoff:1": 1, "body:char_a": 1})
    assert cut.status == "consistent"
    assert cut.checkpoint.last_global_sequence == 2
    restored = replay.checkpoint_plus_tail_replay(cut.checkpoint, [])
    assert restored.projection_hash == replay.full_replay(store.read_events()).projection_hash
    assert store.get_by_idempotency("player:local", "idempotency:handoff:1").transaction_id == committed.transaction_id
    assert len(store.read_events()) == 2


def test_cut_rejects_stale_owner_pins_without_writing_checkpoint():
    from app.world_runtime.replay_checkpoint import capture_replay_cut

    store = GameplayEventStore()
    store.append_batch(_batch())
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={"session:handoff:1": 0})
    assert cut.status == "incomplete"
    assert cut.checkpoint is None
    assert "owner_revision_mismatch" in cut.diagnostics
    assert store.list_projection_checkpoints() == []


def test_owner_commit_during_cut_is_incomplete_instead_of_mixed_latest_snapshot():
    from app.world_runtime.replay_checkpoint import capture_replay_cut

    class ConcurrentCommitStore(GameplayEventStore):
        def read_events(self, **kwargs):
            prefix = super().read_events(**kwargs)
            self.append_batch(_batch())
            return prefix

    store = ConcurrentCommitStore()
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    assert cut.status == "incomplete"
    assert cut.checkpoint is None
    assert "cut_changed_during_capture" in cut.diagnostics
    assert store.get_last_global_sequence() == 2


def test_checkpoint_tail_missing_events_remains_failed_in_existing_decoder():
    from app.world_runtime.replay_checkpoint import capture_replay_cut, replay_cut_tail

    store = GameplayEventStore()
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    store.append_batch(_batch())
    failed = replay_cut_tail(cut=cut, replay=replay, events=store.read_events()[1:],
                             to_global_sequence=2)
    assert failed.status == "incomplete"
    assert failed.result is None
    assert "event_tail_gap" in failed.diagnostics


def test_tail_digest_mismatch_is_divergent_and_does_not_save_new_facts():
    from app.world_runtime.replay_checkpoint import capture_replay_cut, replay_cut_tail

    store = GameplayEventStore()
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    store.append_batch(_batch())
    result = replay_cut_tail(cut=cut, replay=replay, events=store.read_events(),
                             to_global_sequence=2, expected_result_digest="wrong")
    assert result.status == "divergent"
    assert result.result is None
    assert store.get_last_global_sequence() == 2


def test_tail_rejects_conflicting_events_at_one_global_sequence():
    from app.world_runtime.replay_checkpoint import capture_replay_cut, replay_cut_tail

    store = GameplayEventStore()
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    store.append_batch(_batch())
    events = store.read_events()
    conflicting = events[0].model_copy(update={"event_id": "conflict", "stream_id": "injected"})
    result = replay_cut_tail(cut=cut, replay=replay, events=events + [conflicting], to_global_sequence=2)
    assert result.status == "divergent"
    assert result.result is None


def test_tail_allows_exact_duplicate_delivery():
    from app.world_runtime.replay_checkpoint import capture_replay_cut, replay_cut_tail

    store = GameplayEventStore()
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    store.append_batch(_batch())
    events = store.read_events()
    result = replay_cut_tail(cut=cut, replay=replay, events=events + events, to_global_sequence=2)
    assert result.status == "verified"
    assert result.result.projection_hash == replay.full_replay(events).projection_hash


def test_tail_rejects_unknown_event_before_checkpoint():
    from app.world_runtime.replay_checkpoint import capture_replay_cut, replay_cut_tail

    store = GameplayEventStore()
    store.append_batch(_batch())
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    injected = store.read_events()[0].model_copy(update={"event_id": "injected"})
    result = replay_cut_tail(cut=cut, replay=replay, events=[injected], to_global_sequence=2)
    assert result.status == "divergent"
    assert result.result is None


def test_tail_rejects_reused_event_id_at_another_sequence():
    from app.world_runtime.replay_checkpoint import capture_replay_cut, replay_cut_tail

    store = GameplayEventStore()
    replay = GameplayProjectionReplay(projector_id="world-cut", projector_version="1")
    cut = capture_replay_cut(store=store, replay=replay, expected_owner_revisions={})
    store.append_batch(_batch())
    events = store.read_events()
    reused = events[1].model_copy(update={"event_id": events[0].event_id})
    result = replay_cut_tail(cut=cut, replay=replay, events=[events[0], reused], to_global_sequence=2)
    assert result.status == "divergent"
    assert result.result is None
