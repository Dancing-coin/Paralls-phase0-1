"""Actual Resource owners supply Soul evidence; no source flags from content."""
import importlib
from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.resource_materialization import ResourceMaterializationAuthorityService
from app.gameplay.resource_body_runtime import (
    ResourceBodyRuntimeProjector, ResourceDefinition, ResourceDefinitionRegistry,
    ResourceBodyActionSettlementService, GameplayActionSettlementCommand,
    GameplayActionRequirement, ResourceReservationAuthorityService, ResourceReservationCommand,
)
from app.gameplay.settlement_plan import build_atomic_event_batch


ACTOR = 'char_a'
STREAM = 'gameplay:resources:char_a'
PROFILES = Path(__file__).resolve().parents[2] / 'assets/characters/profiles'


def _api():
    assert importlib.util.find_spec('app.gameplay.soul_sources') is not None, 'Soul original Resource source adapter missing'
    return importlib.import_module('app.gameplay.soul_sources')


def _reader(store):
    definitions = ResourceDefinitionRegistry()
    definitions.register(ResourceDefinition(resource_id='core.stamina', definition_version='character-template:char_a@1', minimum=0, maximum=100))
    definitions.register(ResourceDefinition(resource_id='mental:focus', definition_version='focus@1', minimum=0, maximum=100))
    definitions.register(ResourceDefinition(resource_id='core.stamina', definition_version='stamina@2', minimum=0, maximum=100))
    return _api().SoulResourceSourceReader(store=store, definitions=definitions)


def _pin(**changes):
    return _api().SoulResourceSourcePin.model_validate(dict(actor_ref=ACTOR, world_ref='world:bakery',
        timeline_ref='timeline:main', resource_id='core.stamina', definition_version='character-template:char_a@1') | changes)


def _genesis(store):
    owner = ResourceMaterializationAuthorityService(store=store, registry=CharacterProfileRegistry.from_directory(PROFILES))
    return owner.materialize(actor_ref=ACTOR, world_ref='world:bakery', timeline_ref='timeline:main',
        world_tick=0, idempotency_key='genesis', expected_revision=0)


def _action(store):
    projector = ResourceBodyRuntimeProjector()
    return ResourceBodyActionSettlementService(store=store).settle(GameplayActionSettlementCommand(
        command_id='soul-source-action', actor_ref=ACTOR, authority_principal='resource_body_action_authority',
        idempotency_key='action', payload_digest='original-request', causation_id='cause:source', correlation_id='corr:source',
        requirement=GameplayActionRequirement(action_ref='walk', stamina_resource_id='core.stamina', stamina_cost=3,
            required_function_id='legs')), resources=projector.rebuild_resources(ACTOR, store.read_stream(STREAM)),
        body=projector.rebuild_body(ACTOR, []), enabled_group_ids=('core.resources', 'core.body_runtime'))


def test_resource_source_from_real_genesis_action_and_sqlite_reopen(tmp_path):
    path = tmp_path / 'soul-source.sqlite3'
    store = DurableGameplayEventStore(path)
    _genesis(store)
    assert _action(store).accepted
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        before = restored.read_events()
        source = _reader(restored).read(_pin())
        assert source.entry.current == 97
        assert dict(source.read_revisions) == {STREAM: 4}
        assert source.source_event_refs == tuple(event.event_id for event in restored.read_stream(STREAM))
        assert restored.read_events() == before
    finally:
        restored.close()


def test_resource_source_reservation_chain_uses_current_not_available():
    store = GameplayEventStore()
    _genesis(store)
    projector = ResourceBodyRuntimeProjector()
    owner = ResourceReservationAuthorityService(store=store)
    common = dict(actor_ref=ACTOR, authority_principal='gameplay_authority', payload_digest='source-reservation',
        causation_id='cause:reserve', correlation_id='corr:reserve', resource_id='core.stamina', reservation_ref='reservation:source', lock_ref='lock:source')
    reserve = ResourceReservationCommand(command_id='reserve-source', idempotency_key='reserve', operation='reserve', amount=4, **common)
    assert owner.apply(reserve, resources=projector.rebuild_resources(ACTOR, store.read_stream(STREAM))).committed
    entry = _reader(store).read(_pin()).entry
    assert (entry.current, entry.available, entry.locked) == (100, 96, 4)
    consume = ResourceReservationCommand(command_id='consume-source', idempotency_key='consume', operation='consume', **common)
    assert owner.apply(consume, resources=projector.rebuild_resources(ACTOR, store.read_stream(STREAM))).committed
    assert _reader(store).read(_pin()).entry.current == 96


def test_absent_resource_is_unknown_and_empty_stream_head_is_retained():
    store = GameplayEventStore()
    source = _reader(store).read(_pin(resource_id='mental:focus', definition_version='focus@1'))
    assert source.entry is None
    assert dict(source.read_revisions) == {STREAM: 0}
    _genesis(store)
    source = _reader(store).read(_pin(resource_id='mental:focus', definition_version='focus@1'))
    assert source.entry is None
    assert dict(source.read_revisions) == {STREAM: 3}


@pytest.mark.parametrize('changes', [dict(world_ref='world:main'), dict(timeline_ref='timeline:other')])
def test_source_rejects_cross_world_or_timeline(changes):
    store = GameplayEventStore()
    _genesis(store)
    before = store.read_events()
    with pytest.raises(ValueError, match='soul_resource_scope_mismatch'):
        _reader(store).read(_pin(**changes))
    assert store.read_events() == before


@pytest.mark.parametrize('principal,event_type', [
    ('fixture', 'gameplay.resource.adjusted'),
    ('resource_body_action_authority', 'gameplay.resource.adjusted'),
    ('resource_recovery_authority', 'gameplay.resource.recovered'),
])
def test_source_rejects_probe_forged_companion_and_unsupported_producer(principal, event_type):
    store = GameplayEventStore()
    _genesis(store)
    assert store.append_batch(build_atomic_event_batch(command_id='forged', principal_ref=principal, stream_id=STREAM,
        expected_revision=3, event_specs=[(event_type, dict(actor_ref=ACTOR, resource_id='core.stamina', delta=-1))],
        idempotency_key='forged', causation_id='cause:fake', correlation_id='corr:fake')).committed
    before = store.read_events()
    with pytest.raises(ValueError, match='soul_resource_source_'):
        _reader(store).read(_pin())
    assert store.read_events() == before


def test_source_validates_full_original_receipt_not_membership_id_only(monkeypatch):
    store = GameplayEventStore()
    _genesis(store)
    action = _action(store)
    receipt = action.append_result
    original = store.get_by_idempotency
    def partial(principal, key):
        result = original(principal, key)
        if result and result.transaction_id == receipt.transaction_id:
            return result.model_copy(update={'committed_event_ids': result.committed_event_ids[:1]})
        return result
    monkeypatch.setattr(store, 'get_by_idempotency', partial)
    with pytest.raises(ValueError, match='soul_resource_source_receipt'):
        _reader(store).read(_pin())


def test_source_pin_cannot_register_arbitrary_owner_or_payload_path():
    with pytest.raises(ValueError):
        _pin(principal_ref='my-package', success_field='allowed')


def test_every_stream_event_matches_original_batch_even_after_transaction_cache(monkeypatch):
    store = GameplayEventStore()
    _genesis(store)
    original = store.read_stream
    def corrupted(stream, **kwargs):
        events = original(stream, **kwargs)
        if stream == STREAM:
            events[1] = events[1].model_copy(update={'payload': dict(events[1].payload, current=1)}, deep=True)
        return events
    monkeypatch.setattr(store, 'read_stream', corrupted)
    with pytest.raises(ValueError, match='soul_resource_source_receipt'):
        _reader(store).read(_pin())


def test_existing_resource_with_wrong_policy_version_is_not_absence():
    store = GameplayEventStore()
    _genesis(store)
    with pytest.raises(ValueError, match='soul_resource_source_definition_version'):
        _reader(store).read(_pin(definition_version='stamina@2'))


def test_modern_action_source_rejects_noncanonical_request_digest(monkeypatch):
    store = GameplayEventStore()
    _genesis(store)
    action = _action(store)
    transaction = store.get_transaction(action.append_result.transaction_id)
    record = transaction.idempotency_record.model_copy(update={'payload_digest': 'opaque-modern-digest'})
    damaged = transaction.model_copy(update={'idempotency_record': record})
    get_transaction, get_record = store.get_transaction, store.get_idempotency_record
    monkeypatch.setattr(store, 'get_transaction', lambda ref: damaged if ref == damaged.transaction_id else get_transaction(ref))
    monkeypatch.setattr(store, 'get_idempotency_record', lambda principal, key:
        record if (principal, key) == (record.principal_ref, record.idempotency_key) else get_record(principal, key))
    with pytest.raises(ValueError, match='soul_resource_source_action'):
        _reader(store).read(_pin())
