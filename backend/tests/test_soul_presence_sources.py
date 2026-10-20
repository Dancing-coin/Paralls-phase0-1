"""Soul identity evidence uses the actual Presence/activation owners."""
import importlib
from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import PopulationPresenceAuthority, CharacterSpawnRequest, CharacterDespawnRequest


WORLD, PROFILE, ACTOR = 'world:bakery', 'character:char_a', 'char_a'
POPULATION, PRESENCE = f'population:{WORLD}', f'presence:{WORLD}'
LIFE = f'gameplay:character:life:{PROFILE}'


def _api():
    assert importlib.util.find_spec('app.gameplay.soul_presence_sources'), 'Soul Presence source reader missing'
    return importlib.import_module('app.gameplay.soul_presence_sources')


def _composition(store):
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / 'assets/characters/profiles')
    grant = ActivationGrant(profile_ref=PROFILE, world_ref=WORLD, package_revision='package:1',
        policy_revision='policy:1', scope_grant=('actor:self',))
    activation = ProfileActivationAuthority(store=store, registry=registry, grants=(grant,))
    presence = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=activation, producer_ref='population:district-authority'))
    return activation, presence


def _spawn(activation, presence, *, key='one', population_revision=0, presence_revision=0):
    receipt = activation.commit(ActivationProposal(proposal_id=f'activation:{key}', profile_ref=PROFILE,
        world_ref=WORLD, package_revision='package:1', policy_revision='policy:1', scope_grant=('actor:self',),
        cadence_class='active', activation_reason='scene admission', source_ref='population:district-authority',
        expected_revisions={POPULATION: population_revision}, idempotency_key=f'activation:{key}', correlation_id='correlation:one'))
    assert receipt.committed
    result = presence.spawn(CharacterSpawnRequest(world_ref=WORLD, character_ref=PROFILE,
        activation_event_id=receipt.committed_event_ids[0], idempotency_key=f'spawn:{key}', expected_revision=presence_revision))
    assert result.committed
    return result


def _read(presence, **changes):
    return _api().SoulPresenceSourceReader(presence=presence).read(actor_ref=ACTOR, world_ref=WORLD, **changes)


def test_actual_presence_identity_source_and_sqlite_reopen(tmp_path):
    path = tmp_path / 'presence.sqlite3'
    store = DurableGameplayEventStore(path)
    activation, presence = _composition(store)
    receipt = _spawn(activation, presence)
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        _, presence = _composition(restored)
        before = restored.read_events()
        source = _read(presence)
        assert source.actor_ref == ACTOR and source.world_ref == WORLD and source.incarnation == 1
        assert source.presence_event_id == receipt.committed_event_ids[0]
        assert source.activation_event_id == receipt.source_activation_event_id
        assert dict(source.read_revisions) == {POPULATION: 1, PRESENCE: 1, LIFE: 0}
        assert set(source.source_event_refs) == {event.event_id for event in before}
        assert source.last_global_sequence == before[-1].global_sequence
        with pytest.raises(TypeError):
            source.read_revisions[LIFE] = 20
        assert restored.read_events() == before
    finally:
        restored.close()


def test_absent_inactive_and_changed_incarnation_never_reuse_an_old_anchor():
    store = GameplayEventStore()
    activation, presence = _composition(store)
    with pytest.raises(ValueError, match='soul_presence_source_absent'):
        _read(presence)
    _spawn(activation, presence)
    assert presence.despawn(CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE,
        incarnation=1, expected_revision=1, idempotency_key='despawn', reason='leave')).committed
    with pytest.raises(ValueError, match='soul_presence_source_absent'):
        _read(presence)
    _spawn(activation, presence, key='two', population_revision=1, presence_revision=2)
    assert _read(presence).incarnation == 2
    with pytest.raises(ValueError, match='soul_presence_source_incarnation'):
        _read(presence, expected_incarnation=1)


def test_current_activation_and_life_are_not_inferred_from_original_spawn():
    store = GameplayEventStore()
    activation, presence = _composition(store)
    _spawn(activation, presence)
    assert activation.suspend(WORLD, PROFILE, expected_revision=1).committed
    with pytest.raises(ValueError, match='activation_source_inactive'):
        _read(presence)


def test_even_non_dead_life_history_is_unavailable_without_life_owner_adapter():
    store = GameplayEventStore()
    activation, presence = _composition(store)
    _spawn(activation, presence)
    assert store.append_batch(build_atomic_event_batch(command_id='life', principal_ref='fixture', stream_id=LIFE,
        expected_revision=0, event_specs=[('gameplay.character.life_state_changed', {'to_state': 'alive'})],
        idempotency_key='life', causation_id='life', correlation_id='life')).committed
    with pytest.raises(ValueError, match='soul_presence_source_life_unavailable'):
        _read(presence)


@pytest.mark.parametrize('actor', ['character:char_a', 'actor:char_a', 'npc:char_a', ''])
def test_only_canonical_actor_id_is_accepted(actor):
    _, presence = _composition(GameplayEventStore())
    with pytest.raises(ValueError, match='soul_presence_source_actor'):
        _api().SoulPresenceSourceReader(presence=presence).read(actor_ref=actor, world_ref=WORLD)


def test_source_reads_original_fixed_presence_cut_during_despawn_race(monkeypatch):
    store = GameplayEventStore()
    activation, presence = _composition(store)
    _spawn(activation, presence)
    read = store.read_stream
    raced = False

    def race(stream, **kwargs):
        nonlocal raced
        if stream == PRESENCE and not raced:
            raced = True
            assert presence.despawn(CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE,
                incarnation=1, expected_revision=1, idempotency_key='race', reason='leave')).committed
        return read(stream, **kwargs)

    monkeypatch.setattr(store, 'read_stream', race)
    source = _read(presence)
    assert source.incarnation == 1 and source.read_revisions[PRESENCE] == 1
    assert store.get_stream_head(PRESENCE) == 2
    with pytest.raises(ValueError, match='soul_presence_source_absent'):
        _read(presence)


def test_source_rechecks_current_grants_after_presence_was_committed():
    store = GameplayEventStore()
    activation, presence = _composition(store)
    _spawn(activation, presence)
    registry = activation.registry
    removed = ProfileActivationAuthority(store=store, registry=registry, grants=())
    current = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=removed, producer_ref='population:district-authority'))
    with pytest.raises(ValueError, match='activation_source_grants_required'):
        _read(current)


def test_source_rejects_presence_receipt_tampering(monkeypatch):
    store = GameplayEventStore()
    activation, presence = _composition(store)
    _spawn(activation, presence)
    original = store.get_by_idempotency
    def damaged(principal, key):
        receipt = original(principal, key)
        if principal == 'population.presence_authority' and receipt is not None:
            return receipt.model_copy(update={'committed_event_ids': []})
        return receipt
    monkeypatch.setattr(store, 'get_by_idempotency', damaged)
    with pytest.raises(ValueError, match='presence_original_receipt_invalid'):
        _read(presence)
