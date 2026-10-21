from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.social_spatial_owner import SocialSpatialOwner


def _kwargs(**overrides):
    value = dict(actor_ref="character:char_b", target_ref="character:char_a", action_profile="approach",
                 request_ref="execution:turn:1:0", turn_id="turn:1", idempotency_key="exec:1",
                 causation_id="cause:1", correlation_id="corr:1", producer_ts=10,
                 expected_revision_vector={"session:char_b": 3}, expected_memory_revision_vector={"memory:char_b": 4},
                 expected_snapshot_revision=5)
    value.update(overrides)
    return value


def test_social_spatial_owner_commits_receipt_and_exact_replay():
    owner = SocialSpatialOwner(store=GameplayEventStore())
    first = owner.submit(**_kwargs())
    replay = owner.submit(**_kwargs())
    assert first.committed
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == first.committed_event_ids
    assert len(owner.replay("character:char_b")) == 1


def test_social_spatial_owner_rejects_changed_duplicate_without_write():
    owner = SocialSpatialOwner(store=GameplayEventStore())
    assert owner.submit(**_kwargs()).committed
    changed = owner.submit(**_kwargs(action_profile="withdraw"))
    assert not changed.committed
    assert changed.failure.error_code == "social_spatial_idempotency_key_reused"
    assert len(owner.replay("character:char_b")) == 1


def test_social_spatial_owner_rejects_unauthorized_caller():
    owner = SocialSpatialOwner(store=GameplayEventStore())
    result = owner.submit(**_kwargs(authorized_caller="godot"))
    assert not result.committed
    assert result.failure.error_code == "social_spatial_caller_not_authorized"


def test_social_spatial_owner_receipt_replays_after_store_reopen(tmp_path):
    path = tmp_path / "social-spatial.json"
    first_store = DurableGameplayEventStore(path)
    first = SocialSpatialOwner(store=first_store)
    receipt = first.submit(**_kwargs())
    assert receipt.committed
    first_store.close()

    restored_store = DurableGameplayEventStore(path)
    restored = SocialSpatialOwner(store=restored_store)
    replay = restored.submit(**_kwargs())
    assert replay.idempotency_status == "duplicate_replayed"
    assert replay.committed_event_ids == receipt.committed_event_ids
    assert len(restored.replay("character:char_b")) == 1
    restored_store.close()
