"""Presence admission consumes real activation receipts and deployment grants."""
import importlib
from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationGrant, ActivationProposal


WORLD = 'world:bakery'
PROFILE = 'character:char_a'
PRODUCER = 'population:district-authority'
STREAM = f'population:{WORLD}'
PROFILES = Path(__file__).resolve().parents[2] / 'assets/characters/profiles'


def _api():
    assert importlib.util.find_spec('app.population_continuity.activation_sources'), 'closed activation source adapter missing'
    return importlib.import_module('app.population_continuity.activation_sources')


def _authority(store, *, grants=True):
    grant = ActivationGrant(profile_ref=PROFILE, world_ref=WORLD, package_revision='package:1',
        policy_revision='policy:1', scope_grant=('actor:self',))
    return ProfileActivationAuthority(store=store, registry=CharacterProfileRegistry.from_directory(PROFILES),
        grants=(grant,) if grants else ())


def _reader(authority):
    return _api().ActivationSourceReader(authority=authority, producer_ref=PRODUCER)


def _activate(authority, **changes):
    value = dict(proposal_id='activation:one', profile_ref=PROFILE, world_ref=WORLD,
        package_revision='package:1', policy_revision='policy:1', activation_reason='scene admission',
        scope_grant=('actor:self',), cadence_class='active', expected_revisions={STREAM: 0},
        idempotency_key='activate:one', correlation_id='correlation:one', source_ref=PRODUCER)
    receipt = authority.commit(ActivationProposal(**(value | changes)))
    assert receipt.committed
    return receipt.committed_event_ids[0]


def test_actual_activation_sqlite_reopen_and_original_recovery(tmp_path):
    path = tmp_path / 'activation.sqlite3'
    store = DurableGameplayEventStore(path)
    event_id = _activate(_authority(store))
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        authority = _authority(reopened)
        reader = _reader(authority)
        before = reopened.read_events()
        source = reader.read(event_id, world_ref=WORLD, profile_ref=PROFILE)
        assert source.identity_digest == authority.registry.authored_identity_digest(PROFILE)
        assert dict(source.read_revisions) == {STREAM: 1}
        assert source.source_event_refs == (event_id,)
        assert source.last_global_sequence == 1
        with pytest.raises(TypeError):
            source.read_revisions[STREAM] = 20
        # Historical validation never resolves current content/grants.
        authority.registry = CharacterProfileRegistry({})
        authority.grants = ()
        assert reader.recover(event_id, world_ref=WORLD, profile_ref=PROFILE).event_id == event_id
        with pytest.raises(ValueError, match='activation_source_profile'):
            reader.read(event_id, world_ref=WORLD, profile_ref=PROFILE)
        assert reopened.read_events() == before
    finally:
        reopened.close()


def test_empty_legacy_grants_cannot_bootstrap_presence():
    authority = _authority(GameplayEventStore(), grants=False)
    event_id = _activate(authority)  # legacy authority itself permits this
    reader = _reader(authority)
    with pytest.raises(ValueError, match='activation_source_grants_required'):
        reader.read(event_id, world_ref=WORLD, profile_ref=PROFILE)
    assert reader.recover(event_id, world_ref=WORLD, profile_ref=PROFILE).event_id == event_id


@pytest.mark.parametrize('producer', ['population:untrusted', 'world_runtime.activation_authority', 'world_runtime.cadence'])
def test_prefix_is_not_a_trusted_activation_producer(producer):
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority, source_ref=producer)
    with pytest.raises(ValueError, match='activation_source_producer'):
        _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE)


def test_grant_snapshot_is_deeply_immutable_and_new_composition_rechecks_grants():
    authority = _authority(GameplayEventStore())
    reader = _reader(authority)
    object.__setattr__(authority.grants[0], 'scope_grant', ('actor:self', 'world:write'))
    event_id = _activate(authority, scope_grant=('world:write',))
    with pytest.raises(ValueError, match='activation_source_grant'):
        reader.read(event_id, world_ref=WORLD, profile_ref=PROFILE)
    assert _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE).event_id == event_id
    assert reader.recover(event_id, world_ref=WORLD, profile_ref=PROFILE).event_id == event_id


@pytest.mark.parametrize('operation', ['suspend', 'requeue', 'lock'])
def test_only_current_activation_admits_but_old_receipt_survives_lifecycle(operation):
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority)
    if operation == 'lock':
        result = authority.lock(world_ref=WORLD, profile_ref=PROFILE, expected_revision=1)
    else:
        result = getattr(authority, operation)(WORLD, PROFILE, expected_revision=1)
    assert result.committed
    reader = _reader(authority)
    with pytest.raises(ValueError, match='activation_source_inactive'):
        reader.read(event_id, world_ref=WORLD, profile_ref=PROFILE)
    assert reader.recover(event_id, world_ref=WORLD, profile_ref=PROFILE).event_id == event_id
    new_id = _activate(authority, proposal_id='activation:two', idempotency_key='activate:two', expected_revisions={STREAM: 2})
    assert reader.read(new_id, world_ref=WORLD, profile_ref=PROFILE).event_id == new_id


def test_region_assignment_is_not_deactivation():
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority)
    # A non-lifecycle Population event must not replace the activation state.
    batch = build_atomic_event_batch(command_id='region', principal_ref='world_runtime.activation_authority',
        stream_id=STREAM, expected_revision=1, event_specs=[('population.activation.region_assigned',
            {'world_ref': WORLD, 'profile_ref': PROFILE, 'region_ref': 'region:one'})],
        idempotency_key='region', causation_id='region', correlation_id='region')
    assert authority.store.append_batch(batch).committed
    source = _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE)
    assert dict(source.read_revisions) == {STREAM: 2}


@pytest.mark.parametrize('change', ['digest', 'schema', 'extra_payload', 'expected', 'pins', 'receipt', 'member', 'record', 'status'])
def test_original_transaction_and_receipt_tampering_rejects(monkeypatch, change):
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority)
    store = authority.store
    event = store.get_event(event_id)
    batch = store.get_transaction(event.transaction_id).model_copy(deep=True)
    original_transaction = store.get_transaction
    original_receipt = store.get_by_idempotency
    original_record = store.get_idempotency_record
    if change == 'digest':
        batch.result_digest = 'forged'
    elif change == 'schema':
        batch.events[0].schema_version = 2
    elif change == 'extra_payload':
        batch.events[0].payload['accepted'] = True
    elif change == 'expected':
        batch.expected_stream_revisions = {STREAM: 10}
    elif change == 'pins':
        batch.pinned_revisions = {}
    elif change == 'receipt':
        receipt = original_receipt(PRODUCER, 'activate:one').model_copy(update={'committed_event_ids': []})
        monkeypatch.setattr(store, 'get_by_idempotency', lambda *args: receipt)
    elif change == 'record':
        monkeypatch.setattr(store, 'get_idempotency_record', lambda *args: None)
    elif change == 'status':
        receipt = original_receipt(PRODUCER, 'activate:one').model_copy(update={'idempotency_status': 'rejected'})
        monkeypatch.setattr(store, 'get_by_idempotency', lambda *args: receipt)
    elif change == 'member':
        batch.events[0] = batch.events[0].model_copy(update={'correlation_id': 'another'})
    if change not in ('receipt', 'record'):
        monkeypatch.setattr(store, 'get_transaction', lambda tx: batch if tx == batch.transaction_id else original_transaction(tx))
    with pytest.raises(ValueError, match='activation_source_'):
        _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE)


def test_cross_world_and_profile_are_rejected():
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority)
    reader = _reader(authority)
    for changes in ({'world_ref': 'world:elsewhere'}, {'profile_ref': 'character:char_b'}):
        with pytest.raises(ValueError, match='activation_source_'):
            reader.read(event_id, **(dict(world_ref=WORLD, profile_ref=PROFILE) | changes))


def test_captured_head_is_not_replaced_by_a_concurrently_newer_lifecycle(monkeypatch):
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority)
    read_stream = authority.store.read_stream
    raced = False

    def race(stream_id, **kwargs):
        nonlocal raced
        if not raced:
            raced = True
            assert authority.suspend(WORLD, PROFILE, expected_revision=1).committed
        return read_stream(stream_id, **kwargs)

    monkeypatch.setattr(authority.store, 'read_stream', race)
    source = _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE)
    assert source.read_revisions[STREAM] == 1
    assert authority.store.get_stream_head(STREAM) == 2
    # This source is usable only in a consumer append that CAS-checks head1.
    with pytest.raises(ValueError, match='activation_source_inactive'):
        _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE)


@pytest.mark.parametrize('field', ['profile_ref', 'event_type'])
def test_indexed_lifecycle_cannot_hide_behind_profile_or_type_filter(monkeypatch, field):
    authority = _authority(GameplayEventStore())
    event_id = _activate(authority)
    assert authority.suspend(WORLD, PROFILE, expected_revision=1).committed
    read_stream = authority.store.read_stream

    def corrupt(stream, **kwargs):
        events = [item.model_copy(deep=True) for item in read_stream(stream, **kwargs)]
        if field == 'profile_ref':
            events[-1].payload['profile_ref'] = 'character:char_b'
        else:
            events[-1].event_type = 'population.activation.region_assigned'
        return events

    monkeypatch.setattr(authority.store, 'read_stream', corrupt)
    with pytest.raises(ValueError, match='activation_source_'):
        _reader(authority).read(event_id, world_ref=WORLD, profile_ref=PROFILE)

