"""Soul anchors bind genuine owner evidence without granting Soul operations."""
import importlib
from pathlib import Path

import pytest

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.resource_materialization import ResourceMaterializationAuthorityService
from app.gameplay.resource_body_runtime import ResourceDefinition, ResourceDefinitionRegistry
from app.gameplay.soul_sources import SoulResourceSourcePin, SoulResourceSourceReader
from app.gameplay.soul_presence_sources import SoulPresenceSourceReader
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_sources import ActivationSourceReader
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import PopulationPresenceAuthority, CharacterSpawnRequest, CharacterDespawnRequest

WORLD, ACTOR, PROFILE = 'world:bakery', 'char_a', 'character:char_a'
POPULATION, PRESENCE, RESOURCE = f'population:{WORLD}', f'presence:{WORLD}', f'gameplay:resources:{ACTOR}'
LIFE = f'gameplay:character:life:{PROFILE}'


def _api():
    assert importlib.util.find_spec('app.gameplay.soul_runtime'), 'Soul anchor owner missing'
    return importlib.import_module('app.gameplay.soul_runtime')


def _sources(store, *, spawn=True):
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / 'assets/characters/profiles')
    activation = ProfileActivationAuthority(store=store, registry=registry,
        grants=(ActivationGrant(profile_ref=PROFILE, world_ref=WORLD, package_revision='package:1',
            policy_revision='policy:1', scope_grant=('actor:self',)),))
    presence = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=activation, producer_ref='population:district-authority'))
    if spawn:
        result = activation.commit(ActivationProposal(proposal_id='anchor-activation', profile_ref=PROFILE,
            world_ref=WORLD, package_revision='package:1', policy_revision='policy:1', scope_grant=('actor:self',),
            cadence_class='active', activation_reason='anchor admission', source_ref='population:district-authority',
            expected_revisions={POPULATION: 0}, idempotency_key='anchor-activation', correlation_id='anchor'))
        assert result.committed
        assert presence.spawn(CharacterSpawnRequest(world_ref=WORLD, character_ref=PROFILE,
            activation_event_id=result.committed_event_ids[0], idempotency_key='anchor-spawn', expected_revision=0)).committed
        ResourceMaterializationAuthorityService(store=store, registry=registry).materialize(actor_ref=ACTOR,
            world_ref=WORLD, timeline_ref='timeline:main', world_tick=0, expected_revision=0, idempotency_key='anchor-resource')
    definitions = ResourceDefinitionRegistry()
    definitions.register(ResourceDefinition(resource_id='core.stamina', definition_version='character-template:char_a@1', minimum=0, maximum=100))
    return activation, presence, SoulResourceSourceReader(store=store, definitions=definitions)


def _registration(**changes):
    return _api().SoulAnchorRegistration.model_validate(dict(world_ref=WORLD, package_ref='soul:bounded',
        version='1', timeline_ref='timeline:main', lifetime='until_revoked',
        resource_pins=(SoulResourceSourcePin(actor_ref=ACTOR, world_ref=WORLD, timeline_ref='timeline:main',
            resource_id='core.stamina', definition_version='character-template:char_a@1'),)) | changes)


def _owner(store, presence, resources, registrations=None):
    return _api().SoulAnchorAuthority(store=store, presence_sources=SoulPresenceSourceReader(presence=presence),
        resource_sources=resources, registrations=(_registration(),) if registrations is None else registrations)


def _request(**changes):
    return _api().SoulAnchorRequest.model_validate(dict(actor_ref=ACTOR, world_ref=WORLD,
        package_ref='soul:bounded', version='1', incarnation=1, expected_revision=0,
        idempotency_key='anchor:one') | changes)


def test_anchor_real_sources_commit_and_original_receipt_reopen(tmp_path):
    path = tmp_path / 'anchor.sqlite3'
    store = DurableGameplayEventStore(path)
    _, presence, resources = _sources(store)
    owner = _owner(store, presence, resources)
    result = owner.issue(_request())
    assert result.committed and result.incarnation == 1
    event = store.get_event(result.committed_event_ids[0])
    assert event.visibility_policy == 'authority_only'
    batch = store.get_transaction(event.transaction_id)
    assert batch.read_stream_revisions == {POPULATION: 1, PRESENCE: 1, LIFE: 0, RESOURCE: 3}
    projection = owner.projection(world_ref=WORLD, actor_ref=ACTOR)
    assert projection['incarnation'] == 1
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        _, presence, resources = _sources(restored, spawn=False)
        recovered = _owner(restored, presence, resources, registrations=())
        before = restored.read_events()
        retry = recovered.issue(_request(expected_revision=9))
        assert retry.committed and retry.zero_write and retry.committed_event_ids == result.committed_event_ids
        assert recovered.projection(world_ref=WORLD, actor_ref=ACTOR) == projection
        assert restored.read_events() == before
    finally:
        restored.close()


def test_missing_registration_and_absent_presence_fail_closed():
    store = GameplayEventStore()
    _, presence, resources = _sources(store, spawn=False)
    assert _owner(store, presence, resources, registrations=()).issue(_request()).stop_reason == 'soul_anchor_registration'
    assert _owner(store, presence, resources).issue(_request()).stop_reason == 'soul_presence_source_absent'
    assert not store.read_events()


def test_changed_retry_and_duplicate_anchor_cannot_rebind():
    store = GameplayEventStore()
    _, presence, resources = _sources(store)
    owner = _owner(store, presence, resources)
    assert owner.issue(_request()).committed
    before = store.read_events()
    assert not owner.issue(_request(incarnation=2)).committed
    assert owner.issue(_request(idempotency_key='another', expected_revision=1)).stop_reason == 'soul_anchor_already_bound'
    assert store.read_events() == before


def test_presence_advance_between_read_and_append_rejects_atomically(monkeypatch):
    store = GameplayEventStore()
    _, presence, resources = _sources(store)
    owner = _owner(store, presence, resources)
    append = store.append_batch
    raced = False
    def race(batch):
        nonlocal raced
        if not raced:
            raced = True
            assert presence.despawn(CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE,
                incarnation=1, expected_revision=1, idempotency_key='anchor-race', reason='leave')).committed
        return append(batch)
    monkeypatch.setattr(store, 'append_batch', race)
    result = owner.issue(_request())
    assert not result.committed
    assert not owner.projection(world_ref=WORLD, actor_ref=ACTOR)


def test_policy_is_closed_immutable_and_not_a_permission_string():
    api = _api()
    for extra in [dict(principal_ref='admin'), dict(expires_at=10), dict(lifetime='forever')]:
        with pytest.raises(ValueError):
            _registration(**extra)
    for extra in [dict(allowed=True), dict(vulnerable=True), dict(issuer_ref='admin')]:
        with pytest.raises(ValueError):
            _request(**extra)
    store = GameplayEventStore()
    _, presence, resources = _sources(store)
    with pytest.raises(ValueError, match='soul_anchor_registration_duplicate'):
        _owner(store, presence, resources, registrations=(_registration(), _registration()))
    with pytest.raises(ValueError):
        _registration().version = 'changed'


def test_anchor_history_rejects_corrupt_original_receipt(monkeypatch):
    store = GameplayEventStore()
    _, presence, resources = _sources(store)
    owner = _owner(store, presence, resources)
    assert owner.issue(_request()).committed
    get = store.get_by_idempotency
    def damage(principal, key):
        result = get(principal, key)
        if principal == 'soul.anchor_authority' and result is not None:
            return result.model_copy(update={'global_sequence_range': (0, 0)})
        return result
    monkeypatch.setattr(store, 'get_by_idempotency', damage)
    assert not owner.issue(_request()).committed
    with pytest.raises(ValueError, match='soul_anchor_original'):
        owner.projection(world_ref=WORLD, actor_ref=ACTOR)


def test_anchor_history_rejects_resource_pin_from_another_timeline():
    store = GameplayEventStore()
    _, presence, resources = _sources(store)
    owner = _owner(store, presence, resources)
    assert owner.issue(_request()).committed
    projection = owner.projection(world_ref=WORLD, actor_ref=ACTOR)
    projection['resource_pins'][0]['timeline_ref'] = 'timeline:other'
    event = store.read_stream(owner.stream_id(WORLD, ACTOR))[0]
    batch = store.get_transaction(event.transaction_id)
    with pytest.raises(ValueError, match='soul_anchor_original'):
        owner._validate_source_cut(projection, batch.read_stream_revisions, event.global_sequence)
