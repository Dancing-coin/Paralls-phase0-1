"""Real activation -> Presence owner -> original recovery and lifecycle replay."""
from pathlib import Path
import hashlib
import json

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.gameplay.event_schema_registry import EventSchemaRegistration, EventSchemaRegistry, EventSchemaRegistryError
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import (
    CharacterSpawnRequest, CharacterDespawnRequest, PopulationPresenceAuthority,
)


WORLD, PROFILE = 'world:bakery', 'character:char_a'
POPULATION, PRESENCE = f'population:{WORLD}', f'presence:{WORLD}'
LIFE = f'gameplay:character:life:{PROFILE}'
PRODUCER = 'population:district-authority'


def _composition(store):
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / 'assets/characters/profiles')
    grant = ActivationGrant(profile_ref=PROFILE, world_ref=WORLD, package_revision='package:1',
        policy_revision='policy:1', scope_grant=('actor:self',))
    activation = ProfileActivationAuthority(store=store, registry=registry, grants=(grant,))
    source = ActivationSourceReader(authority=activation, producer_ref=PRODUCER)
    return activation, PopulationPresenceAuthority(store=store, activation_sources=source)


def _activate(activation, *, key='one', expected=0):
    receipt = activation.commit(ActivationProposal(proposal_id=f'activation:{key}', profile_ref=PROFILE,
        world_ref=WORLD, package_revision='package:1', policy_revision='policy:1', scope_grant=('actor:self',),
        cadence_class='active', activation_reason='scene admission', source_ref=PRODUCER,
        expected_revisions={POPULATION: expected}, idempotency_key=f'activation:{key}', correlation_id='correlation:one'))
    assert receipt.committed
    return receipt.committed_event_ids[0]


def _spawn(event_id, *, expected=0, key='spawn:one'):
    return CharacterSpawnRequest(world_ref=WORLD, character_ref=PROFILE, activation_event_id=event_id,
        expected_revision=expected, idempotency_key=key)


def _despawn(*, expected=1, incarnation=1, key='despawn:one'):
    return CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE, incarnation=incarnation,
        expected_revision=expected, idempotency_key=key, reason='leave scene')


def test_real_owner_full_incarnation_chain_original_recovery_and_sqlite_reopen(tmp_path):
    path = tmp_path / 'presence.sqlite3'
    store = DurableGameplayEventStore(path)
    activation, presence = _composition(store)
    source_id = _activate(activation)
    first = presence.spawn(_spawn(source_id))
    assert first.committed and first.incarnation == 1
    original = store.get_transaction(store.get_event(first.committed_event_ids[0]).transaction_id)
    assert original.read_stream_revisions == {POPULATION: 1, LIFE: 0}
    assert presence.despawn(_despawn()).committed
    second = presence.spawn(_spawn(source_id, expected=2, key='spawn:two'))
    assert second.committed and second.incarnation == 2
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        activation, presence = _composition(restored)
        assert activation.suspend(WORLD, PROFILE, expected_revision=1).committed
        activation.registry = CharacterProfileRegistry({})
        activation.grants = ()
        before = restored.read_events()
        duplicate = presence.spawn(_spawn(source_id, expected=3))
        assert duplicate.committed and duplicate.idempotency_status == 'duplicate_replayed'
        assert duplicate.incarnation == 1 and duplicate.zero_write
        assert duplicate.committed_event_ids == first.committed_event_ids
        assert presence.despawn(_despawn(expected=3)).idempotency_status == 'duplicate_replayed'
        assert presence.projection(WORLD) == {PROFILE: {'incarnation': 2, 'status': 'present'}}
        first_sequence = restored.get_event(first.committed_event_ids[0]).global_sequence
        assert presence.projection(WORLD, checkpoint_at=first_sequence) == {PROFILE: {'incarnation': 1, 'status': 'present'}}
        assert restored.read_events() == before
    finally:
        restored.close()


def test_source_configuration_missing_or_cross_store_cannot_spawn():
    store = GameplayEventStore()
    activation, _ = _composition(store)
    source_id = _activate(activation)
    denied = PopulationPresenceAuthority(store=store).spawn(_spawn(source_id))
    assert not denied.committed and denied.zero_write
    with pytest.raises(ValueError, match='presence_source_store'):
        PopulationPresenceAuthority(store=GameplayEventStore(),
            activation_sources=ActivationSourceReader(authority=activation, producer_ref=PRODUCER))


@pytest.mark.parametrize('to_state', ['dead', 'alive'])
def test_any_life_history_blocks_new_spawn_without_a_named_life_adapter(to_state):
    store = GameplayEventStore()
    activation, presence = _composition(store)
    source_id = _activate(activation)
    assert store.append_batch(build_atomic_event_batch(command_id='untrusted-life', principal_ref='fixture',
        stream_id=LIFE, expected_revision=0, event_specs=[('gameplay.character.life_state_changed', {'to_state': to_state})],
        idempotency_key='life', causation_id='life', correlation_id='life')).committed
    before = store.read_events()
    result = presence.spawn(_spawn(source_id))
    assert not result.committed and result.stop_reason == 'life_source_unavailable' and result.zero_write
    assert store.read_events() == before


@pytest.mark.parametrize('source', ['activation', 'life_absence'])
def test_source_racing_spawn_is_rejected_by_the_original_read_cas(monkeypatch, source):
    store = GameplayEventStore()
    activation, presence = _composition(store)
    source_id = _activate(activation)
    append = store.append_batch
    raced = False

    def race(batch):
        nonlocal raced
        if not raced and batch.events[0].event_type == 'population.presence.spawned':
            raced = True
            if source == 'activation':
                assert activation.suspend(WORLD, PROFILE, expected_revision=1).committed
            else:
                assert append(build_atomic_event_batch(command_id='life-race', principal_ref='fixture',
                    stream_id=LIFE, expected_revision=0, event_specs=[('gameplay.character.life_state_changed', {'to_state': 'alive'})],
                    idempotency_key='life-race', causation_id='life-race', correlation_id='life-race')).committed
        return append(batch)

    monkeypatch.setattr(store, 'append_batch', race)
    result = presence.spawn(_spawn(source_id))
    assert not result.committed and store.get_stream_head(PRESENCE) == 0


def test_future_expected_head_is_rejected_before_despawn_projection(monkeypatch):
    store = GameplayEventStore()
    activation, presence = _composition(store)
    assert presence.spawn(_spawn(_activate(activation))).committed
    read = store.read_stream
    scanned = []

    def observed(stream, **kwargs):
        scanned.append(stream)
        return read(stream, **kwargs)

    monkeypatch.setattr(store, 'read_stream', observed)
    result = presence.despawn(_despawn(expected=2))
    assert not result.committed and result.stop_reason == 'revision_conflict'
    assert PRESENCE not in scanned


@pytest.mark.parametrize('change', ['digest', 'status', 'index', 'missing'])
def test_corrupt_original_presence_receipt_or_index_rejects(monkeypatch, change):
    store = GameplayEventStore()
    activation, presence = _composition(store)
    source_id = _activate(activation)
    result = presence.spawn(_spawn(source_id))
    assert result.committed
    original_tx = store.get_transaction
    original_receipt = store.get_by_idempotency
    original_read = store.read_stream
    if change == 'digest':
        def bad_tx(ref):
            batch = original_tx(ref)
            if batch and batch.events[0].stream_id == PRESENCE:
                return batch.model_copy(update={'result_digest': 'forged'})
            return batch
        monkeypatch.setattr(store, 'get_transaction', bad_tx)
    elif change == 'status':
        def bad_receipt(principal, key):
            receipt = original_receipt(principal, key)
            return receipt.model_copy(update={'idempotency_status': 'rejected'}) if principal == 'population.presence_authority' else receipt
        monkeypatch.setattr(store, 'get_by_idempotency', bad_receipt)
    elif change == 'index':
        def bad_index(stream, **kwargs):
            events = original_read(stream, **kwargs)
            if stream == PRESENCE:
                events = [item.model_copy(deep=True) for item in events]
                events[0].payload['character_ref'] = 'character:char_b'
            return events
        monkeypatch.setattr(store, 'read_stream', bad_index)
    else:
        original_get = store.get_event
        def missing(ref):
            if ref == result.committed_event_ids[0]:
                raise KeyError(ref)
            return original_get(ref)
        monkeypatch.setattr(store, 'get_event', missing)
    with pytest.raises(ValueError, match='presence_'):
        presence.projection(WORLD)
    if change != 'index':
        denied = presence.spawn(_spawn(source_id))
        assert not denied.committed and denied.zero_write


def test_legal_receipt_with_orphan_incarnation_is_not_a_valid_history():
    store = GameplayEventStore()
    activation, presence = _composition(store)
    source_id = _activate(activation)
    request = _spawn(source_id)
    digest = 'sha256:' + hashlib.sha256(json.dumps({'operation': 'spawned', 'request': request.model_dump(mode='json')},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    forged = build_atomic_event_batch(command_id=f'presence:spawn:{WORLD}:{PROFILE}:3',
        principal_ref='population.presence_authority', stream_id=PRESENCE, expected_revision=0,
        event_specs=[('population.presence.spawned', dict(world_ref=WORLD, character_ref=PROFILE, incarnation=3,
            source_activation_event_id=source_id, request_digest=digest))], idempotency_key=request.idempotency_key,
        causation_id=source_id, correlation_id=f'correlation:{WORLD}',
        read_stream_revisions={POPULATION: 1, LIFE: 0}, pinned_revisions={POPULATION: 1, LIFE: 0})
    assert store.append_batch(forged).committed
    with pytest.raises(ValueError, match='presence_'):
        presence.projection(WORLD)


def test_changed_duplicate_and_wrong_incarnation_are_zero_write():
    store = GameplayEventStore()
    activation, presence = _composition(store)
    source_id = _activate(activation)
    assert presence.spawn(_spawn(source_id)).committed
    before = store.read_events()
    changed = _spawn(source_id).model_copy(update={'activation_event_id': 'other'})
    assert not presence.spawn(changed).committed
    assert not presence.despawn(_despawn(incarnation=2)).committed
    assert store.read_events() == before


def test_presence_schema_opt_in_is_complete_idempotent_and_excludes_life():
    from app.population_continuity.presence_runtime import register_presence_event_schemas
    schemas = EventSchemaRegistry()
    register_presence_event_schemas(schemas)
    register_presence_event_schemas(schemas)
    with pytest.raises(EventSchemaRegistryError):
        schemas.get('gameplay.character.life_state_changed', 2)
    # Activation owns its schema separately; this test composes the two owners.
    schemas.register(EventSchemaRegistration('population.activation.committed', 1, 'sha256:activation:v1'))
    store = GameplayEventStore(event_schema_registry=schemas)
    activation, presence = _composition(store)
    assert presence.spawn(_spawn(_activate(activation))).committed
    assert presence.despawn(_despawn()).committed
