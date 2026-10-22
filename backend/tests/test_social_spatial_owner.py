from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.social_spatial_owner import SocialSpatialOwner
from app.gameplay.settlement_plan import build_atomic_event_batch


def _kwargs(**overrides):
    value = dict(actor_ref="character:char_b", target_ref="character:char_a", action_profile="approach",
                 request_ref="execution:turn:1:0", turn_id="turn:1", idempotency_key="exec:1",
                 causation_id="cause:1", correlation_id="corr:1", producer_ts=10,
                 expected_revision_vector={"session:char_b": 3}, expected_memory_revision_vector={"memory:char_b": 4},
                 expected_snapshot_revision=5)
    value.update(overrides)
    return value


def _source_event(store, stream, event_type, payload):
    return store.get_event(store.append_batch(build_atomic_event_batch(
        command_id=f"source:{stream}:{store.get_stream_head(stream) + 1}",
        principal_ref="test:source", stream_id=stream,
        expected_revision=store.get_stream_head(stream),
        event_specs=((event_type, payload),),
        idempotency_key=f"source:{stream}:{store.get_stream_head(stream) + 1}",
        causation_id="test:cause", correlation_id="test:corr",
    )).committed_event_ids[0])


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


def test_social_spatial_owner_rechecks_source_read_set_before_append():
    store = GameplayEventStore()
    source_stream = "presence:world:demo"
    source = _source_event(store, source_stream, "population.presence.spawned", {
        "world_ref": "world:demo", "character_ref": "character:char_a", "incarnation": 1,
    })
    result = SocialSpatialOwner(store=store).submit(**_kwargs(
        source_read_set={source_stream: source.stream_revision},
        source_context={"actor_presence_event": source.event_id},
    ))
    assert result.committed
    assert store.get_event(result.committed_event_ids[0]).payload["source_read_set"] == {source_stream: 1}


def test_social_spatial_owner_rejects_stale_source_read_set_without_write():
    store = GameplayEventStore()
    stream = "presence:world:demo"
    first = _source_event(store, stream, "population.presence.spawned", {"world_ref": "world:demo", "character_ref": "character:char_a", "incarnation": 1})
    owner = SocialSpatialOwner(store=store)
    _source_event(store, stream, "population.presence.despawned", {"world_ref": "world:demo", "character_ref": "character:char_a", "incarnation": 1, "reason": "test"})
    before = store.get_last_global_sequence()
    result = owner.submit(**_kwargs(source_read_set={stream: first.stream_revision}))
    assert not result.committed
    assert result.failure.error_code == "social_spatial_source_stale"
    assert store.get_last_global_sequence() == before


def test_social_spatial_source_pins_recover_after_durable_reopen_and_source_change(tmp_path):
    path = tmp_path / "social-source.db"
    stream = "presence:world:demo"
    store = DurableGameplayEventStore(path)
    source = _source_event(store, stream, "population.presence.spawned", {"world_ref": "world:demo", "character_ref": "character:char_a", "incarnation": 1})
    request = _kwargs(source_read_set={stream: source.stream_revision}, source_context={"presence_event": source.event_id})
    receipt = SocialSpatialOwner(store=store).submit(**request)
    assert receipt.committed
    transaction = store.get_transaction(receipt.transaction_id)
    assert transaction.read_stream_revisions == request["source_read_set"]
    _source_event(store, stream, "population.presence.despawned", {"world_ref": "world:demo", "character_ref": "character:char_a", "incarnation": 1, "reason": "test"})
    store.close()

    store = DurableGameplayEventStore(path)
    owner = SocialSpatialOwner(store=store)
    before = store.get_last_global_sequence()
    replay = owner.submit(**request)
    assert replay.committed_event_ids == receipt.committed_event_ids
    assert replay.idempotency_status == "duplicate_replayed"
    changed = owner.submit(**dict(request, source_read_set={stream: 2}))
    assert not changed.committed
    assert store.get_last_global_sequence() == before
    store.close()
