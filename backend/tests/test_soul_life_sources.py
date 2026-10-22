from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.life_state_runtime import CanonicalLifeStateAuthority
from app.gameplay.soul_life_sources import SoulLifeSourceReader
from app.gameplay.soul_presence_sources import SoulPresenceSourceReader
from app.gameplay.life_state_runtime import CaseDeathLifeStateCaller
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import (
    CharacterSpawnRequest,
    PopulationPresenceAuthority,
)


WORLD = "world:bakery"
PROFILE = "character:char_a"
ACTOR = "char_a"
POPULATION = f"population:{WORLD}"
PRESENCE = f"presence:{WORLD}"
LIFE = f"gameplay:character:life:{PROFILE}"


def _composition(store):
    registry = CharacterProfileRegistry.from_directory(
        Path(__file__).resolve().parents[2] / "assets/characters/profiles"
    )
    grant = ActivationGrant(profile_ref=PROFILE, world_ref=WORLD, package_revision="package:1",
        policy_revision="policy:1", scope_grant=("actor:self",))
    activation = ProfileActivationAuthority(store=store, registry=registry, grants=(grant,))
    presence = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=activation,
            producer_ref="population:district-authority"))
    return activation, presence


def _spawn_and_initialize(store):
    activation, presence = _composition(store)
    committed = activation.commit(ActivationProposal(proposal_id="activation:life", profile_ref=PROFILE,
        world_ref=WORLD, package_revision="package:1", policy_revision="policy:1", scope_grant=("actor:self",),
        cadence_class="active", activation_reason="scene admission", source_ref="population:district-authority",
        expected_revisions={POPULATION: 0}, idempotency_key="activation:life", correlation_id="correlation:life"))
    assert committed.committed
    spawned = presence.spawn(CharacterSpawnRequest(world_ref=WORLD, character_ref=PROFILE,
        activation_event_id=committed.committed_event_ids[0], idempotency_key="presence:life", expected_revision=0))
    assert spawned.committed
    result = CanonicalLifeStateAuthority(store=store).initialize_alive_from_presence(
        activation_event_id=committed.committed_event_ids[0], presence_event_id=spawned.committed_event_ids[0],
        expected_activation_revision=1, expected_presence_revision=1, command_id="life:initialize",
        idempotency_key="life:initialize", causation_id=spawned.committed_event_ids[0],
        correlation_id="life:initialize")
    assert result.committed
    return presence, result.committed_event_ids[0]


def test_real_life_owner_source_is_rebuilt_at_fixed_head_and_reopen(tmp_path):
    path = tmp_path / "life.sqlite3"
    store = DurableGameplayEventStore(path)
    _, life_event_id = _spawn_and_initialize(store)
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        source = SoulLifeSourceReader(store=restored).read(
            actor_ref=ACTOR, world_ref=WORLD, incarnation=1, boundary_revision=1)
        assert source.state == "alive"
        assert life_event_id in source.source_event_refs
        assert source.read_revisions[LIFE] == 1
        assert source.last_global_sequence == restored.get_event(life_event_id).global_sequence
        with pytest.raises(ValueError, match="soul_life_source_revision"):
            SoulLifeSourceReader(store=restored).read(actor_ref=ACTOR, world_ref=WORLD,
                                                       incarnation=1, boundary_revision=2)
    finally:
        restored.close()


def test_presence_source_includes_only_owner_verified_alive_state():
    store = GameplayEventStore()
    presence, life_event_id = _spawn_and_initialize(store)
    life = SoulLifeSourceReader(store=store)
    source = SoulPresenceSourceReader(presence=presence, life_sources=life).read(
        actor_ref=ACTOR, world_ref=WORLD)
    assert source.read_revisions[LIFE] == 1
    assert life_event_id in source.source_event_refs


def test_presence_source_rejects_untrusted_life_reader_implementation():
    store = GameplayEventStore()
    presence, _ = _spawn_and_initialize(store)

    class ForgedLifeReader:
        _store = store

        def read(self, **_):
            return type("Life", (), {"state": "alive"})()

    with pytest.raises(ValueError, match="soul_presence_source_life_authority"):
        SoulPresenceSourceReader(presence=presence, life_sources=ForgedLifeReader())


def test_life_source_rejects_unowned_or_tampered_history():
    store = GameplayEventStore()
    _, life_event_id = _spawn_and_initialize(store)
    original = store.get_event(life_event_id)
    store._events_by_id[life_event_id] = original.model_copy(
        update={"payload": {**original.payload, "to_state": "dead"}}, deep=True)
    store._events = [store.get_event(event.event_id) for event in store._events]
    with pytest.raises(ValueError, match="soul_life_source_receipt|soul_life_source_history|soul_life_source_transition"):
        SoulLifeSourceReader(store=store).read(actor_ref=ACTOR, world_ref=WORLD, incarnation=1)


def test_confirmed_death_is_verified_but_not_projected_without_incarnation_binding():
    from test_life_state_case_death_caller import _seed

    store, confirmation_id = _seed(actor_ref="character:death:1")
    result = CaseDeathLifeStateCaller(store=store).record_confirmed_case_death(
        confirmation_event_id=confirmation_id, expected_source_revision=2,
        command_id="life:confirmed-death", idempotency_key="life:confirmed-death",
        causation_id=confirmation_id, correlation_id="life:confirmed-death")
    assert result.result.committed
    with pytest.raises(ValueError, match="soul_life_source_death_scope_unbound"):
        SoulLifeSourceReader(store=store).read(actor_ref="death:1", world_ref="world:case", incarnation=1)
