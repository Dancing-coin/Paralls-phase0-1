"""Bounded Soul effects consume real four-gate sources in one append CAS."""
import importlib

import pytest

from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.gameplay.soul_fact_runtime import SoulFactAuthority
from test_soul_fact_owner import _setup, _command
from test_soul_vulnerability import _gate
from test_soul_anchor_owner import WORLD, ACTOR, PROFILE, RESOURCE
from app.population_continuity.presence_runtime import CharacterDespawnRequest
from test_soul_resource_sources import _action


def _api():
    assert importlib.util.find_spec('app.gameplay.soul_effect_runtime'), 'Soul effect owner missing'
    return importlib.import_module('app.gameplay.soul_effect_runtime')


def _registration(**changes):
    return _api().SoulEffectRegistration.model_validate(dict(world_ref=WORLD,
        package_ref='soul:bounded', version='1', rule_ref='effect:binding',
        value_ref='binding:ritual', vulnerability_rule_ref='test:explicit-mind-mapping',
        link_rule_ref='rule:link', grant_rule_ref='rule:grant', precedence=1,
        lifetime='until_revoked') | changes)


def _request(**changes):
    return _api().SoulEffectRequest.model_validate(dict(world_ref=WORLD,
        actor_ref=ACTOR, target_ref=ACTOR, actor_incarnation=1, target_incarnation=1,
        package_ref='soul:bounded', version='1', rule_ref='effect:binding', operation='bind',
        expected_revision=0, idempotency_key='effect:one') | changes)


def _owner(store, *, initialize=True, issue=('link', 'grant'), registrations=None):
    presence, anchors, facts = _setup(store, initialize=initialize)
    if initialize:
        for revision, kind in enumerate(issue):
            assert facts.settle(_command(rule_ref=f'rule:{kind}', expected_revision=revision,
                idempotency_key=f'fact:{kind}')).committed
    owner = _api().SoulEffectAuthority(facts=facts, vulnerability=_gate(anchors),
        registrations=(_registration(),) if registrations is None else registrations)
    return presence, facts, owner


def test_bind_and_explicit_counterplay_write_only_soul_and_pin_all_gates():
    store = GameplayEventStore()
    _, facts, owner = _owner(store)
    result = owner.settle(_request())
    assert result.committed and not result.zero_write
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == 'soul.effect.binding.changed'
    assert event.visibility_policy == 'authority_only'
    assert event.payload['value_ref'] == 'binding:ritual' and event.payload['active'] is True
    batch = store.get_transaction(event.transaction_id)
    assert batch.read_stream_revisions[facts.stream_id(WORLD, ACTOR)] == 2
    assert batch.read_stream_revisions[RESOURCE] == 3
    assert batch.read_stream_revisions[f'gameplay:character:life:{PROFILE}'] == 0
    assert batch.pinned_revisions == batch.read_stream_revisions
    before_resource = store.get_stream_head(RESOURCE)
    assert not owner.settle(_request(idempotency_key='conflicting', expected_revision=1)).committed
    reversed_result = owner.settle(_request(operation='unbind', original_effect_ref=event.event_id,
        idempotency_key='effect:reverse', expected_revision=1))
    assert reversed_result.committed
    assert not owner.projection(world_ref=WORLD, target_ref=ACTOR)['active']
    assert store.get_stream_head(RESOURCE) == before_resource
    before = store.read_events()
    retry = owner.settle(_request(expected_revision=999))
    assert retry.committed and retry.zero_write and retry.committed_event_ids == result.committed_event_ids
    assert store.read_events() == before


@pytest.mark.parametrize('issue,reason', [((), 'soul_effect_link'), (('link',), 'soul_effect_grant')])
def test_missing_owner_fact_is_zero_write(issue, reason):
    store = GameplayEventStore()
    _, _, owner = _owner(store, issue=issue)
    before = store.read_events()
    result = owner.settle(_request())
    assert not result.committed and result.stop_reason == reason
    assert store.read_events() == before


@pytest.mark.parametrize('rank,allowed', [(0, False), (1, True), (2, True)])
def test_target_protection_precedence_and_absence_are_owner_reads(rank, allowed):
    store = GameplayEventStore()
    _, facts, _ = _owner(store, issue=('link', 'grant', 'protection'))
    owner = _api().SoulEffectAuthority(facts=facts, vulnerability=_gate(facts._anchors),
        registrations=(_registration(precedence=rank),))
    before = store.read_events()
    result = owner.settle(_request())
    assert result.committed is allowed
    if not allowed:
        assert result.stop_reason == 'soul_effect_protection'
        assert store.read_events() == before


def test_resource_gate_is_current_and_unknown_cannot_be_caller_overridden():
    from test_soul_vulnerability import _registration as vulnerability_registration, _branch
    store = GameplayEventStore()
    _, facts, _ = _owner(store)
    gate = _gate(facts._anchors, (vulnerability_registration(branches=(_branch(threshold=97),)),))
    owner = _api().SoulEffectAuthority(facts=facts, vulnerability=gate, registrations=(_registration(),))
    before = store.read_events()
    assert owner.settle(_request()).stop_reason == 'soul_effect_vulnerability'
    assert store.read_events() == before
    assert _action(store).accepted
    result = owner.settle(_request())
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert store.get_transaction(event.transaction_id).read_stream_revisions[RESOURCE] == 4
    with pytest.raises(ValueError):
        _request(allowed=True, vulnerable=True)


def test_revoked_grant_and_despawn_reject_new_effects_but_recover_original():
    store = GameplayEventStore()
    presence, facts, owner = _owner(store)
    committed = owner.settle(_request())
    assert committed.committed
    grant = facts.projection(_command(rule_ref='rule:grant'))
    assert facts.settle(_command(rule_ref='rule:grant', operation='revoke',
        original_fact_ref=grant['original_fact_ref'], expected_revision=2,
        idempotency_key='revoke:grant')).committed
    before = store.read_events()
    result = owner.settle(_request(operation='unbind', original_effect_ref=committed.committed_event_ids[0],
        expected_revision=1, idempotency_key='new:reverse'))
    assert result.stop_reason == 'soul_effect_grant'
    assert store.read_events() == before
    assert presence.despawn(CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE,
        incarnation=1, expected_revision=1, idempotency_key='effect:leave', reason='leave')).committed
    before = store.read_events()
    assert owner.settle(_request()).zero_write
    assert not owner.settle(_request(idempotency_key='effect:new', expected_revision=1)).committed
    assert store.read_events() == before


@pytest.mark.parametrize('source', ['resource', 'grant'])
def test_source_advance_between_gate_and_append_rejects(source, monkeypatch):
    store = GameplayEventStore()
    _, facts, owner = _owner(store)
    append = store.append_batch
    raced = False

    def advance(batch):
        nonlocal raced
        if not raced and not isinstance(batch, dict) and batch.idempotency_record.principal_ref == 'soul.effect_authority':
            raced = True
            if source == 'resource':
                assert _action(store).accepted
            else:
                grant = facts.projection(_command(rule_ref='rule:grant'))
                assert facts.settle(_command(rule_ref='rule:grant', operation='revoke',
                    original_fact_ref=grant['original_fact_ref'], expected_revision=2,
                    idempotency_key='race:grant')).committed
        return append(batch)

    monkeypatch.setattr(store, 'append_batch', advance)
    result = owner.settle(_request())
    assert raced and not result.committed
    assert store.get_stream_head(owner.stream_id(WORLD, ACTOR)) == 0


def test_original_receipt_reopens_without_current_policy_and_changed_retry_rejects(tmp_path):
    path = tmp_path / 'effects.sqlite3'
    store = DurableGameplayEventStore(path)
    _, _, owner = _owner(store)
    request = _request()
    result = owner.settle(request)
    assert result.committed
    projection = owner.projection(world_ref=WORLD, target_ref=ACTOR)
    store.close()
    reopened = DurableGameplayEventStore(path)
    try:
        _, _, recovered = _owner(reopened, initialize=False, registrations=())
        before = reopened.read_events()
        retry = recovered.settle(request)
        assert retry.committed and retry.zero_write and retry.committed_event_ids == result.committed_event_ids
        assert recovered.projection(world_ref=WORLD, target_ref=ACTOR) == projection
        assert not recovered.settle(_request(target_incarnation=2)).committed
        assert not recovered.settle(_request(idempotency_key='new', expected_revision=1)).committed
        assert reopened.read_events() == before
    finally:
        reopened.close()


@pytest.mark.parametrize('changes', [dict(actor_incarnation=2), dict(target_incarnation=2),
    dict(package_ref='soul:other'), dict(version='2'), dict(operation='unbind', original_effect_ref='fake')])
def test_committed_identity_is_complete_and_changed_duplicate_is_zero_write(changes):
    store = GameplayEventStore()
    _, _, owner = _owner(store)
    assert owner.settle(_request()).committed
    before = store.read_events()
    assert not owner.settle(_request(**changes)).committed
    assert store.read_events() == before


def test_facts_must_match_operation_and_full_policy_identity():
    from test_soul_fact_owner import _registration as fact_registration
    store = GameplayEventStore()
    _, anchors, _ = _setup(store)
    facts = SoulFactAuthority(anchors=anchors, registrations=(
        fact_registration('link', operations=('curse',)), fact_registration('grant', operations=('curse',))))
    for revision, kind in enumerate(('link', 'grant')):
        assert facts.settle(_command(rule_ref=f'rule:{kind}', expected_revision=revision,
            idempotency_key=f'only-curse:{kind}')).committed
    owner = _api().SoulEffectAuthority(facts=facts, vulnerability=_gate(anchors), registrations=(_registration(),))
    before = store.read_events()
    assert not owner.settle(_request()).committed
    assert store.read_events() == before


def test_protection_from_another_attacker_and_another_rule_cannot_be_hidden():
    from test_soul_fact_owner import _registration as fact_registration
    store = GameplayEventStore()
    _, anchors, _ = _setup(store)
    facts = SoulFactAuthority(anchors=anchors, registrations=(fact_registration('link'), fact_registration('grant'),
        fact_registration('protection', precedence=10), fact_registration('protection', rule_ref='protection:weak')))
    for revision, rule in enumerate(('rule:link', 'rule:grant', 'rule:protection', 'protection:weak')):
        assert facts.settle(_command(rule_ref=rule, expected_revision=revision,
            idempotency_key=f'multi:{rule}')).committed
    owner = _api().SoulEffectAuthority(facts=facts, vulnerability=_gate(anchors), registrations=(_registration(),))
    before = store.read_events()
    assert owner.settle(_request()).stop_reason == 'soul_effect_protection'
    assert store.read_events() == before


def test_different_anchor_composition_cannot_supply_vulnerability():
    store = GameplayEventStore()
    _, facts, _ = _owner(store)
    other = GameplayEventStore()
    _, _, other_owner = _owner(other)
    with pytest.raises(ValueError, match='soul_effect_sources'):
        _api().SoulEffectAuthority(facts=facts, vulnerability=other_owner._vulnerability,
            registrations=(_registration(),))


@pytest.mark.parametrize('changes', [dict(operation='curse'), dict(operation='unbind'),
    dict(original_effect_ref='forged'), dict(expected_revision=True)])
def test_unsupported_operations_and_invalid_original_refs_reject(changes):
    with pytest.raises(ValueError):
        _request(**changes)


@pytest.mark.parametrize('corruption', ['digest', 'receipt', 'source_cut'])
def test_history_and_exact_retry_reject_corrupted_original(corruption, monkeypatch):
    store = GameplayEventStore()
    _, _, owner = _owner(store)
    result = owner.settle(_request())
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    get_transaction = store.get_transaction
    get_receipt = store.get_by_idempotency
    if corruption == 'receipt':
        def corrupt(principal, key):
            receipt = get_receipt(principal, key)
            return receipt.model_copy(update={'resulting_stream_revisions': {}}) if principal == 'soul.effect_authority' else receipt
        monkeypatch.setattr(store, 'get_by_idempotency', corrupt)
    else:
        def corrupt(transaction_id):
            batch = get_transaction(transaction_id)
            if transaction_id != event.transaction_id:
                return batch
            change = {'result_digest': 'corrupt'} if corruption == 'digest' else {'read_stream_revisions': {}}
            return batch.model_copy(update=change)
        monkeypatch.setattr(store, 'get_transaction', corrupt)
    with pytest.raises(ValueError):
        owner.projection(world_ref=WORLD, target_ref=ACTOR)
    assert not owner.settle(_request()).committed


def test_forged_owner_batch_with_no_gate_sources_is_not_replayable():
    from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch
    source = GameplayEventStore()
    _, _, original_owner = _owner(source)
    result = original_owner.settle(_request())
    original = source.get_event(result.committed_event_ids[0])
    store = GameplayEventStore()
    _, _, owner = _owner(store)
    stream = owner.stream_id(WORLD, ACTOR)
    forged = build_multi_stream_atomic_event_batch(command_id=original.command_id,
        principal_ref='soul.effect_authority', expected_revisions={stream: 0},
        event_specs={stream: [(original.event_type, original.payload)]},
        event_visibility_policies={stream: ['authority_only']}, idempotency_key='effect:one',
        causation_id=original.causation_id, correlation_id=original.correlation_id)
    assert store.append_batch(forged).committed
    with pytest.raises(ValueError):
        owner.projection(world_ref=WORLD, target_ref=ACTOR)
    assert not owner.settle(_request()).committed


def _two_actor_owner(store):
    from pathlib import Path
    from app.character_agent.profile.registry import CharacterProfileRegistry
    from app.population_continuity.activation import ProfileActivationAuthority
    from app.population_continuity.activation_sources import ActivationSourceReader
    from app.population_continuity.models import ActivationGrant, ActivationProposal
    from app.population_continuity.presence_runtime import PopulationPresenceAuthority, CharacterSpawnRequest
    from app.gameplay.resource_materialization import ResourceMaterializationAuthorityService
    from app.gameplay.resource_body_runtime import ResourceDefinition
    from app.gameplay.soul_presence_sources import SoulPresenceSourceReader
    from app.gameplay.soul_runtime import SoulAnchorAuthority
    from app.gameplay.soul_sources import SoulResourceSourcePin
    from test_soul_anchor_owner import _sources, _registration as anchor_registration, _request as anchor_request
    from test_soul_vulnerability import _registration as vulnerability_registration, _branch

    _, _, resources = _sources(store, spawn=False)
    registry = CharacterProfileRegistry.from_directory(Path(__file__).resolve().parents[2] / 'assets/characters/profiles')
    activation = ProfileActivationAuthority(store=store, registry=registry, grants=tuple(
        ActivationGrant(profile_ref=f'character:{actor}', world_ref=WORLD, package_revision='package:1',
            policy_revision='policy:1', scope_grant=('actor:self',)) for actor in ('char_a', 'char_b')))
    presence = PopulationPresenceAuthority(store=store,
        activation_sources=ActivationSourceReader(authority=activation, producer_ref='population:district-authority'))
    for index, actor in enumerate(('char_a', 'char_b')):
        active = activation.commit(ActivationProposal(proposal_id=f'active:{actor}', profile_ref=f'character:{actor}',
            world_ref=WORLD, package_revision='package:1', policy_revision='policy:1', scope_grant=('actor:self',),
            cadence_class='active', activation_reason='effect target test', source_ref='population:district-authority',
            expected_revisions={f'population:{WORLD}': index}, idempotency_key=f'active:{actor}', correlation_id='effect'))
        assert active.committed
        assert presence.spawn(CharacterSpawnRequest(world_ref=WORLD, character_ref=f'character:{actor}',
            activation_event_id=active.committed_event_ids[0], expected_revision=index,
            idempotency_key=f'spawn:{actor}')).committed
        ResourceMaterializationAuthorityService(store=store, registry=registry).materialize(actor_ref=actor,
            world_ref=WORLD, timeline_ref='timeline:main', world_tick=0, expected_revision=0, idempotency_key=f'resource:{actor}')
        if actor != ACTOR:
            resources._definitions.register(ResourceDefinition(resource_id='core.stamina',
                definition_version=f'character-template:{actor}@1', minimum=0, maximum=120))
    # Each existing anchor registration is intentionally actor-specific.
    for actor in ('char_a', 'char_b'):
        anchors = SoulAnchorAuthority(store=store, presence_sources=SoulPresenceSourceReader(presence=presence),
            resource_sources=resources, registrations=(anchor_registration(resource_pins=(SoulResourceSourcePin(
                actor_ref=actor, world_ref=WORLD, timeline_ref='timeline:main', resource_id='core.stamina',
                definition_version=f'character-template:{actor}@1'),)),))
        assert anchors.issue(anchor_request(actor_ref=actor, idempotency_key=f'anchor:{actor}')).committed
    from test_soul_fact_owner import _registration as fact_registration
    facts = SoulFactAuthority(anchors=anchors, registrations=tuple(fact_registration(kind) for kind in ('link', 'grant', 'protection')))
    for revision, kind in enumerate(('link', 'grant')):
        assert facts.settle(_command(target_ref='char_b', rule_ref=f'rule:{kind}', expected_revision=revision,
            idempotency_key=f'pair:{kind}')).committed
    gate = _gate(anchors, (vulnerability_registration(actor_ref='char_b', branches=(
        _branch(definition_version='character-template:char_b@1', threshold=120),)),))
    return presence, facts, _api().SoulEffectAuthority(facts=facts, vulnerability=gate, registrations=(_registration(),))


def test_distinct_target_vulnerability_and_all_active_issuer_absence_heads():
    store = GameplayEventStore()
    _, facts, owner = _two_actor_owner(store)
    result = owner.settle(_request(target_ref='char_b'))
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    batch = store.get_transaction(event.transaction_id)
    assert batch.read_stream_revisions['gameplay:resources:char_b'] == 3
    assert batch.read_stream_revisions[facts.stream_id(WORLD, 'char_b')] == 0
    assert owner.projection(world_ref=WORLD, target_ref='char_b')['active']


def test_first_target_protection_concurrent_issue_cannot_escape_absence_cas(monkeypatch):
    store = GameplayEventStore()
    _, facts, owner = _two_actor_owner(store)
    append = store.append_batch
    raced = False
    def race(batch):
        nonlocal raced
        if not raced and not isinstance(batch, dict) and batch.idempotency_record.principal_ref == 'soul.effect_authority':
            raced = True
            assert facts.settle(_command(actor_ref='char_b', target_ref='char_b', rule_ref='rule:protection',
                expected_revision=0, idempotency_key='first:protection')).committed
        return append(batch)
    monkeypatch.setattr(store, 'append_batch', race)
    assert not owner.settle(_request(target_ref='char_b')).committed
    assert raced and store.get_stream_head(owner.stream_id(WORLD, 'char_b')) == 0


def test_history_replays_each_original_once_per_projection(monkeypatch):
    store = GameplayEventStore()
    _, _, owner = _owner(store)
    original = None
    for revision in range(4):
        result = owner.settle(_request(operation='bind' if revision % 2 == 0 else 'unbind',
            original_effect_ref=None if revision % 2 == 0 else original,
            expected_revision=revision, idempotency_key=f'cycle:{revision}'))
        assert result.committed
        if revision % 2 == 0:
            original = result.committed_event_ids[0]
    replay = type(owner)._replay_original
    calls = []
    def count(self, request, event, batch):
        calls.append(event.event_id)
        return replay(self, request, event, batch)
    monkeypatch.setattr(type(owner), '_replay_original', count)
    assert not owner.projection(world_ref=WORLD, target_ref=ACTOR)['active']
    assert len(calls) == 4
    calls.clear()
    assert not owner.projection(world_ref=WORLD, target_ref=ACTOR)['active']
    assert len(calls) == 4  # Nothing persists across independent reads.
