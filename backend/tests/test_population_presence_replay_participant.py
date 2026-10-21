from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.presence_runtime import (
    CharacterDespawnRequest,
    CharacterSpawnRequest,
    PopulationPresenceAuthority,
)
from app.world_runtime.replay_participants import _presence_participant


def _activate(store, world, character, key):
    result = store.append_batch(build_atomic_event_batch(
        command_id=key,
        principal_ref="world_runtime.activation_authority",
        stream_id=f"population:{world}", expected_revision=0,
        event_specs=[("population.activation.committed", {
            "profile_ref": character, "identity_digest": "sha256:identity", "world_ref": world,
        })], idempotency_key=key, causation_id="cadence", correlation_id=world,
    ))
    assert result.committed
    return result.committed_event_ids[0]


def _spawn(store, authority, world, character, activation, key, revision=0):
    result = authority.spawn(CharacterSpawnRequest(
        world_ref=world, character_ref=character, activation_event_id=activation,
        idempotency_key=key, expected_revision=revision,
    ))
    assert result.committed
    return result


def test_presence_participant_uses_owner_projection_at_bounded_cut_and_isolates_worlds():
    store = GameplayEventStore()
    authority = PopulationPresenceAuthority(store=store)
    a = _activate(store, "world:a", "character:alice", "activation:a")
    b = _activate(store, "world:b", "character:bob", "activation:b")
    first = _spawn(store, authority, "world:a", "character:alice", a, "spawn:a")
    second = _spawn(store, authority, "world:b", "character:bob", b, "spawn:b", revision=0)
    cut = store.get_event(second.committed_event_ids[0]).global_sequence
    later = authority.despawn(CharacterDespawnRequest(
        world_ref="world:a", character_ref="character:alice", incarnation=1,
        idempotency_key="despawn:a", expected_revision=1, reason="window_closed",
    ))
    assert later.committed

    participant = _presence_participant(store, authority, boundary_sequence=cut)
    assert participant["rows"] == [{
        "world_ref": "world:a", "character_ref": "character:alice",
        "incarnation": 1, "status": "present",
    }, {
        "world_ref": "world:b", "character_ref": "character:bob",
        "incarnation": 1, "status": "present",
    }]
    assert participant["reconstruction_api"] == "PopulationPresenceAuthority.projection"
    assert all(ref["global_sequence"] <= cut for ref in participant["event_refs"])


def test_presence_participant_rejects_store_mismatch():
    store = GameplayEventStore()
    authority = PopulationPresenceAuthority(store=store)
    activation = _activate(store, "world:a", "character:alice", "activation:a")
    _spawn(store, authority, "world:a", "character:alice", activation, "spawn:a")
    participant = _presence_participant(store, authority)
    assert participant["view_digest"]
    try:
        _presence_participant(store, PopulationPresenceAuthority(store=GameplayEventStore()))
    except ValueError as exc:
        assert str(exc) == "replay_presence_store_mismatch"
    else:
        raise AssertionError("store mismatch must be rejected")


def test_presence_owner_projection_survives_durable_close_reopen(tmp_path):
    path = tmp_path / "presence-replay.sqlite3"
    store = DurableGameplayEventStore(path)
    authority = PopulationPresenceAuthority(store=store)
    activation = _activate(store, "world:a", "character:alice", "activation:a")
    _spawn(store, authority, "world:a", "character:alice", activation, "spawn:a")
    store.close()
    reopened = DurableGameplayEventStore(path)
    reopened_authority = PopulationPresenceAuthority(store=reopened)
    participant = _presence_participant(reopened, reopened_authority)
    assert participant["rows"][0]["character_ref"] == "character:alice"
    assert reopened_authority.projection("world:a") == {
        "character:alice": {"incarnation": 1, "status": "present"}
    }
    reopened.close()


def test_respawn_after_durable_reopen_allocates_new_incarnation_and_invalidates_old_target(tmp_path):
    path = tmp_path / "presence-incarnation.sqlite3"
    store = DurableGameplayEventStore(path)
    authority = PopulationPresenceAuthority(store=store)
    activation = _activate(store, "world:a", "character:alice", "activation:a")
    first = _spawn(store, authority, "world:a", "character:alice", activation, "spawn:one")
    departed = authority.despawn(CharacterDespawnRequest(
        world_ref="world:a", character_ref="character:alice", incarnation=first.incarnation,
        idempotency_key="despawn:one", expected_revision=1, reason="explicit_departure",
    ))
    assert departed.committed and departed.incarnation == 1
    departed_cut = store.get_event(departed.committed_event_ids[0]).global_sequence
    store.close()

    reopened = DurableGameplayEventStore(path)
    restored = PopulationPresenceAuthority(store=reopened)
    second = _spawn(reopened, restored, "world:a", "character:alice", activation, "spawn:two", revision=2)
    assert second.incarnation == 2
    replay = restored.spawn(CharacterSpawnRequest(
        world_ref="world:a", character_ref="character:alice", activation_event_id=activation,
        idempotency_key="spawn:two", expected_revision=2,
    ))
    assert replay.idempotency_status == "duplicate_replayed" and replay.incarnation == 2
    changed = restored.spawn(CharacterSpawnRequest(
        world_ref="world:a", character_ref="character:alice", activation_event_id=activation,
        idempotency_key="spawn:two", expected_revision=3,
    ))
    assert not changed.committed and changed.stop_reason == "idempotency_key_reused"
    stale = restored.despawn(CharacterDespawnRequest(
        world_ref="world:a", character_ref="character:alice", incarnation=1,
        idempotency_key="despawn:stale-old-target", expected_revision=3, reason="stale_target",
    ))
    assert not stale.committed and stale.stop_reason == "presence_incarnation_not_active"
    current = _presence_participant(reopened, restored)
    at_departure = _presence_participant(reopened, restored, boundary_sequence=departed_cut)
    assert current["rows"] == [{
        "world_ref": "world:a", "character_ref": "character:alice",
        "incarnation": 2, "status": "present",
    }]
    assert at_departure["rows"] == []
    assert all(ref["global_sequence"] <= departed_cut for ref in at_departure["event_refs"])
    reopened.close()
