from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import (
    CharacterDespawnRequest,
    CharacterSpawnRequest,
    PopulationPresenceAuthority,
)


PROFILES = Path(__file__).resolve().parents[2] / "assets/characters/profiles"
PRODUCER = "population:siming"
CHARACTER = "character:char_a"


def _composition(store: GameplayEventStore, *, world_ref: str = "world:one"):
    # Presence only admits a source the activation owner actually committed
    # under a configured grant; hand-built activation events are rejected.
    grant = ActivationGrant(profile_ref=CHARACTER, world_ref=world_ref, package_revision="package:1",
        policy_revision="policy:1", scope_grant=("actor:self",))
    activation = ProfileActivationAuthority(store=store,
        registry=CharacterProfileRegistry.from_directory(PROFILES), grants=(grant,))
    presence = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=activation, producer_ref=PRODUCER))
    return activation, presence


def _activate(activation: ProfileActivationAuthority, *, world_ref: str = "world:one",
              key: str = "one", expected: int = 0) -> str:
    receipt = activation.commit(ActivationProposal(
        proposal_id=f"activation:{key}", profile_ref=CHARACTER, world_ref=world_ref,
        package_revision="package:1", policy_revision="policy:1", scope_grant=("actor:self",),
        cadence_class="active", activation_reason="population-cadence", source_ref=PRODUCER,
        expected_revisions={f"population:{world_ref}": expected},
        idempotency_key=f"activation:{key}", correlation_id=f"correlation:{key}",
    ))
    assert receipt.committed
    return receipt.committed_event_ids[0]


def test_population_presence_requires_activation_and_allocates_new_incarnation() -> None:
    store = GameplayEventStore()
    activation, authority = _composition(store)
    activation_event_id = _activate(activation)

    first = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref=CHARACTER,
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
            character_ref=CHARACTER,
            activation_event_id=activation_event_id,
            idempotency_key="presence:spawn:one",
            expected_revision=0,
        )
    )
    assert replay.committed and replay.idempotency_status == "duplicate_replayed"
    assert replay.incarnation == 1

    despawn = authority.despawn(
        CharacterDespawnRequest(
            world_ref="world:one", character_ref=CHARACTER, incarnation=1,
            idempotency_key="presence:despawn:one", expected_revision=1,
            reason="population_window_closed",
        )
    )
    assert despawn.committed and despawn.incarnation == 1
    second = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one", character_ref=CHARACTER,
            activation_event_id=activation_event_id, idempotency_key="presence:spawn:two",
            expected_revision=2,
        )
    )
    assert second.committed and second.incarnation == 2


def test_population_presence_rejects_unactivated_or_stale_targets_without_write() -> None:
    store = GameplayEventStore()
    activation, authority = _composition(store)
    missing = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref=CHARACTER,
            activation_event_id="event:missing",
            idempotency_key="presence:spawn:missing",
            expected_revision=0,
        )
    )
    assert not missing.committed and missing.stop_reason == "activation_source_missing"
    assert store.read_events() == []

    activation_event_id = _activate(activation)
    first = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref=CHARACTER,
            activation_event_id=activation_event_id,
            idempotency_key="presence:spawn:one",
            expected_revision=0,
        )
    )
    assert first.committed
    before = store.read_events()
    stale = authority.despawn(
        CharacterDespawnRequest(
            world_ref="world:one",
            character_ref=CHARACTER,
            incarnation=99,
            idempotency_key="presence:despawn:stale",
            expected_revision=1,
            reason="population_window_closed",
        )
    )
    assert not stale.committed and stale.stop_reason == "presence_incarnation_not_active"
    assert store.read_events() == before


def test_presence_rejects_inactive_latest_activation_and_any_life_history() -> None:
    store = GameplayEventStore()
    activation, authority = _composition(store)
    activation_event_id = _activate(activation)
    # A lifecycle transition after the source activation closes the admission window.
    assert activation.suspend("world:one", CHARACTER, expected_revision=1).committed
    inactive = authority.spawn(CharacterSpawnRequest(world_ref="world:one", character_ref=CHARACTER,
        activation_event_id=activation_event_id, idempotency_key="spawn:inactive", expected_revision=0))
    assert not inactive.committed and inactive.stop_reason == "activation_source_inactive"

    store = GameplayEventStore()
    activation, authority = _composition(store)
    activation_event_id = _activate(activation)
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="life:dead",
            principal_ref="authority:character:life-state",
            stream_id=f"gameplay:character:life:{CHARACTER}",
            expected_revision=0,
            event_specs=[("gameplay.character.life_state_changed", {"actor_ref": CHARACTER, "from_state": "unknown", "to_state": "dead"})],
            idempotency_key="life:dead",
            causation_id=activation_event_id,
            correlation_id="correlation:world:one",
        )
    ).committed
    # Until a named Life adapter is integrated, Presence cannot interpret life
    # history, so any life fact (death included) blocks a new spawn.
    dead = authority.spawn(CharacterSpawnRequest(world_ref="world:one", character_ref=CHARACTER,
        activation_event_id=activation_event_id, idempotency_key="spawn:dead", expected_revision=0))
    assert not dead.committed and dead.stop_reason == "life_source_unavailable" and dead.zero_write


def test_presence_rejects_old_activation_after_lifecycle_change() -> None:
    store = GameplayEventStore()
    activation, authority = _composition(store)
    activation_event_id = _activate(activation)
    assert activation.suspend("world:one", CHARACTER, expected_revision=1).committed
    newer = _activate(activation, key="two", expected=2)
    assert newer != activation_event_id
    result = authority.spawn(
        CharacterSpawnRequest(
            world_ref="world:one",
            character_ref=CHARACTER,
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
    activation, authority = _composition(store)
    activation_event_id = _activate(activation)
    spawned = authority.spawn(CharacterSpawnRequest(world_ref="world:one", character_ref=CHARACTER,
        activation_event_id=activation_event_id, idempotency_key="spawn:durable", expected_revision=0))
    assert spawned.committed
    store.close()
    reopened = DurableGameplayEventStore(path)
    _, authority = _composition(reopened)
    despawn_request = CharacterDespawnRequest(world_ref="world:one", character_ref=CHARACTER, incarnation=1,
        idempotency_key="despawn:durable", expected_revision=1, reason="window_closed")
    first = authority.despawn(despawn_request)
    replay = authority.despawn(despawn_request)
    assert first.committed and replay.committed and replay.idempotency_status == "duplicate_replayed"
    before = reopened.read_events()
    changed = authority.despawn(despawn_request.model_copy(update={"reason": "other"}))
    # The owner reports any mismatch against the original receipt, a reused key
    # included, as one recovery failure; what matters is that nothing is written.
    assert not changed.committed and changed.zero_write
    assert changed.stop_reason == "presence_original_receipt_invalid"
    assert reopened.read_events() == before
    reopened.close()


def test_spawn_rejects_case_death_committed_after_preflight_before_append(monkeypatch) -> None:
    store = GameplayEventStore()
    activation, authority = _composition(store, world_ref="world:race")
    activation_event_id = _activate(activation, world_ref="world:race")
    original_append = store.append_batch

    def append_with_death(batch):
        if batch.events and batch.events[0].stream_id == "presence:world:race":
            death = original_append(
                build_atomic_event_batch(
                    command_id="life:race-dead",
                    principal_ref="authority:character:life-state",
                    stream_id=f"gameplay:character:life:{CHARACTER}",
                    expected_revision=0,
                    event_specs=[(
                        "gameplay.character.life_state_changed",
                        {"actor_ref": CHARACTER, "from_state": "unknown", "to_state": "dead"},
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
            character_ref=CHARACTER,
            activation_event_id=activation_event_id,
            idempotency_key="spawn:race",
            expected_revision=0,
        )
    )
    assert not result.committed and result.stop_reason == "revision_conflict"
    assert not authority.projection("world:race")
