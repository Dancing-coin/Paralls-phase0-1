from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.presence_runtime import (
    CharacterDespawnRequest,
    CharacterSpawnRequest,
    PopulationPresenceAuthority,
)


def _activate(store: GameplayEventStore, *, world_ref: str, character_ref: str) -> str:
    result = store.append_batch(
        build_atomic_event_batch(
            command_id="activate:one",
            principal_ref="world_runtime.activation_authority",
            stream_id=f"population:{world_ref}",
            expected_revision=0,
            event_specs=[
                (
                    "population.activation.committed",
                    {
                        "profile_ref": character_ref,
                        "identity_digest": "sha256:identity",
                        "world_ref": world_ref,
                    },
                )
            ],
            idempotency_key="activation:one",
            causation_id="cadence:one",
            correlation_id="correlation:one",
        )
    )
    assert result.committed
    return result.committed_event_ids[0]


def test_population_presence_requires_activation_and_allocates_new_incarnation() -> None:
    store = GameplayEventStore()
    activation_event_id = _activate(store, world_ref="world:one", character_ref="character:alice")
    authority = PopulationPresenceAuthority(store=store)

    first = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref="character:alice",
            activation_event_id=activation_event_id,
            idempotency_key="presence:spawn:one",
            expected_revision=0,
        )
    )
    assert first.committed and first.incarnation == 1
    assert first.source_activation_event_id == activation_event_id

    replay = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref="character:alice",
            activation_event_id=activation_event_id,
            idempotency_key="presence:spawn:one",
            expected_revision=0,
        )
    )
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    assert replay.incarnation == 1

    despawn = authority.despawn(
        CharacterDespawnRequest(
            world_ref="world:one", character_ref="character:alice", incarnation=1,
            idempotency_key="presence:despawn:one", expected_revision=1,
            reason="population_window_closed",
        )
    )
    assert despawn.committed and despawn.incarnation == 1
    second = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one", character_ref="character:alice",
            activation_event_id=activation_event_id, idempotency_key="presence:spawn:two",
            expected_revision=2,
        )
    )
    assert second.committed and second.incarnation == 2


def test_population_presence_rejects_unactivated_or_stale_targets_without_write() -> None:
    store = GameplayEventStore()
    authority = PopulationPresenceAuthority(store=store)
    missing = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref="character:missing",
            activation_event_id="event:missing",
            idempotency_key="presence:spawn:missing",
            expected_revision=0,
        )
    )
    assert not missing.committed and missing.stop_reason == "activation_source_missing"
    assert store.read_events() == []

    activation_event_id = _activate(store, world_ref="world:one", character_ref="character:alice")
    first = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref="character:alice",
            activation_event_id=activation_event_id,
            idempotency_key="presence:spawn:one",
            expected_revision=0,
        )
    )
    assert first.committed
    stale = authority.despawn(
        CharacterDespawnRequest(
            world_ref="world:one",
            character_ref="character:alice",
            incarnation=99,
            idempotency_key="presence:despawn:stale",
            expected_revision=1,
            reason="population_window_closed",
        )
    )
    assert not stale.committed and stale.stop_reason == "presence_incarnation_not_active"
    assert len(store.read_events()) == 2


def test_presence_rejects_inactive_latest_activation_and_confirmed_dead() -> None:
    store = GameplayEventStore()
    activation_event_id = _activate(store, world_ref="world:one", character_ref="character:alice")
    authority = PopulationPresenceAuthority(store=store)
    # A lifecycle transition after the source activation closes the admission window.
    lifecycle = store.append_batch(
        build_atomic_event_batch(
            command_id="suspend:world:one:alice",
            principal_ref="world_runtime.activation_authority",
            stream_id="population:world:one",
            expected_revision=1,
            event_specs=[("population.activation.suspended", {"world_ref": "world:one", "profile_ref": "character:alice"})],
            idempotency_key="suspend:world:one:alice",
            causation_id=activation_event_id,
            correlation_id="correlation:world:one",
        )
    )
    assert lifecycle.committed
    inactive = authority.spawn(CharacterSpawnRequest(world_ref="world:one", character_ref="character:alice", activation_event_id=activation_event_id, idempotency_key="spawn:inactive", expected_revision=0))
    assert not inactive.committed and inactive.stop_reason == "activation_source_inactive"

    store = GameplayEventStore()
    activation_event_id = _activate(store, world_ref="world:one", character_ref="character:alice")
    store.append_batch(
        build_atomic_event_batch(
            command_id="life:dead",
            principal_ref="authority:character:life-state",
            stream_id="gameplay:character:life:character:alice",
            expected_revision=0,
            event_specs=[("gameplay.character.life_state_changed", {"actor_ref": "character:alice", "from_state": "unknown", "to_state": "dead"})],
            idempotency_key="life:dead",
            causation_id=activation_event_id,
            correlation_id="correlation:world:one",
        )
    )
    dead = PopulationPresenceAuthority(store=store).spawn(CharacterSpawnRequest(world_ref="world:one", character_ref="character:alice", activation_event_id=activation_event_id, idempotency_key="spawn:dead", expected_revision=1))
    assert not dead.committed and dead.stop_reason == "character_confirmed_dead"


def test_presence_rejects_old_activation_after_new_commit() -> None:
    store = GameplayEventStore()
    activation_event_id = _activate(store, world_ref="world:one", character_ref="character:alice")
    newer = store.append_batch(
        build_atomic_event_batch(
            command_id="activate:two",
            principal_ref="world_runtime.activation_authority",
            stream_id="population:world:one",
            expected_revision=1,
            event_specs=[
                (
                    "population.activation.committed",
                    {
                        "profile_ref": "character:alice",
                        "identity_digest": "sha256:identity",
                        "world_ref": "world:one",
                    },
                )
            ],
            idempotency_key="activation:two",
            causation_id="cadence:two",
            correlation_id="correlation:one",
        )
    )
    assert newer.committed
    result = PopulationPresenceAuthority(store=store).spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref="character:alice",
            activation_event_id=activation_event_id,
            idempotency_key="presence:spawn:old-activation",
            expected_revision=0,
        )
    )
    assert not result.committed
    assert result.stop_reason == "activation_source_inactive"
    assert result.zero_write


def test_presence_durable_reopen_and_despawn_duplicate_contract(tmp_path) -> None:
    path = tmp_path / "presence.sqlite3"
    store = DurableGameplayEventStore(path)
    activation_event_id = _activate(store, world_ref="world:one", character_ref="character:alice")
    authority = PopulationPresenceAuthority(store=store)
    spawned = authority.spawn(CharacterSpawnRequest(world_ref="world:one", character_ref="character:alice", activation_event_id=activation_event_id, idempotency_key="spawn:durable", expected_revision=0))
    assert spawned.committed
    store.close()
    reopened = DurableGameplayEventStore(path)
    authority = PopulationPresenceAuthority(store=reopened)
    despawn_request = CharacterDespawnRequest(world_ref="world:one", character_ref="character:alice", incarnation=1, idempotency_key="despawn:durable", expected_revision=1, reason="window_closed")
    first = authority.despawn(despawn_request)
    replay = authority.despawn(despawn_request)
    assert first.committed and replay.committed and replay.idempotency_status == "duplicate_replayed"
    changed = authority.despawn(despawn_request.model_copy(update={"reason": "other"}))
    assert not changed.committed and changed.stop_reason == "idempotency_key_reused"
    reopened.close()


def test_spawn_rejects_case_death_committed_after_preflight_before_append(monkeypatch) -> None:
    store = GameplayEventStore()
    activation_event_id = _activate(store, world_ref="world:race", character_ref="character:alice")
    authority = PopulationPresenceAuthority(store=store)
    original_append = store.append_batch

    def append_with_death(batch):
        if batch.events and batch.events[0].stream_id == "presence:world:race":
            death = original_append(
                build_atomic_event_batch(
                    command_id="life:race-dead",
                    principal_ref="authority:character:life-state",
                    stream_id="gameplay:character:life:character:alice",
                    expected_revision=0,
                    event_specs=[(
                        "gameplay.character.life_state_changed",
                        {"actor_ref": "character:alice", "from_state": "unknown", "to_state": "dead"},
                    )],
                    idempotency_key="life:race-dead",
                    causation_id=activation_event_id,
                    correlation_id="correlation:world:race",
                )
            )
            assert death.committed
        return original_append(batch)

    monkeypatch.setattr(store, "append_batch", append_with_death)
    result = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:race",
            character_ref="character:alice",
            activation_event_id=activation_event_id,
            idempotency_key="spawn:race",
            expected_revision=0,
        )
    )
    assert not result.committed and result.stop_reason == "revision_conflict"
    assert not authority.projection("world:race")
