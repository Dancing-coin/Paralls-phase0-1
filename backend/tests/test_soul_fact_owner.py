"""Registered Soul facts require live owner-backed anchor admission."""
import importlib

import pytest

from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.population_continuity.presence_runtime import CharacterDespawnRequest
from test_soul_anchor_owner import ACTOR, PROFILE, WORLD, _owner, _request, _sources


def _api():
    assert importlib.util.find_spec('app.gameplay.soul_fact_runtime'), 'Soul fact owner missing'
    return importlib.import_module('app.gameplay.soul_fact_runtime')


def _registration(kind='link', **changes):
    return _api().SoulFactRegistration.model_validate(dict(world_ref=WORLD, package_ref='soul:bounded',
        version='1', rule_ref=f'rule:{kind}', kind=kind, operations=('bind', 'unbind'),
        lifetime='until_revoked', precedence=0) | changes)


def _command(**changes):
    return _api().SoulFactRequest.model_validate(dict(world_ref=WORLD, actor_ref=ACTOR, target_ref=ACTOR,
        actor_incarnation=1, target_incarnation=1, package_ref='soul:bounded', version='1',
        rule_ref='rule:link', operation='issue', original_fact_ref=None,
        expected_revision=0, idempotency_key='soul-fact:one') | changes)


def _setup(store, *, initialize=True, registrations=None):
    _, presence, resources = _sources(store, spawn=initialize)
    anchors = _owner(store, presence, resources)
    if initialize:
        assert anchors.issue(_request()).committed
    facts = _api().SoulFactAuthority(anchors=anchors,
        registrations=tuple(_registration(kind) for kind in ('link', 'grant', 'protection'))
        if registrations is None else registrations)
    return presence, anchors, facts


@pytest.mark.parametrize('kind', ['link', 'grant', 'protection'])
def test_real_anchor_fact_issue_revoke_and_original_retry(kind):
    store = GameplayEventStore()
    _, _, owner = _setup(store)
    command = _command(rule_ref=f'rule:{kind}')
    issued = owner.settle(command)
    assert issued.committed and not issued.zero_write
    event = store.get_event(issued.committed_event_ids[0])
    assert event.visibility_policy == 'authority_only'
    state = owner.projection(command)
    assert state['active'] and state['original_fact_ref'] == event.event_id
    revoked = owner.settle(_command(rule_ref=f'rule:{kind}', operation='revoke',
        original_fact_ref=event.event_id, expected_revision=1, idempotency_key='soul-fact:revoke'))
    assert revoked.committed
    assert not owner.projection(command)['active']
    before = store.read_events()
    retry = owner.settle(command.model_copy(update={'expected_revision': 99}))
    assert retry.committed and retry.zero_write and retry.committed_event_ids == issued.committed_event_ids
    assert store.read_events() == before


def test_original_fact_recovery_after_reopen_without_current_policy_or_presence(tmp_path):
    path = tmp_path / 'facts.sqlite3'
    store = DurableGameplayEventStore(path)
    presence, _, owner = _setup(store)
    command = _command()
    result = owner.settle(command)
    assert result.committed
    assert presence.despawn(CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE,
        incarnation=1, expected_revision=1, idempotency_key='fact-leave', reason='leave')).committed
    store.close()
    restored = DurableGameplayEventStore(path)
    try:
        _, _, reopened = _setup(restored, initialize=False, registrations=())
        before = restored.read_events()
        retry = reopened.settle(command)
        assert retry.committed and retry.zero_write and retry.committed_event_ids == result.committed_event_ids
        assert reopened.projection(command)['original_fact_ref'] == result.committed_event_ids[0]
        assert not reopened.settle(_command(idempotency_key='new', expected_revision=1)).committed
        assert restored.read_events() == before
    finally:
        restored.close()


def test_facts_reject_missing_target_changed_retry_and_wrong_revoke_without_writes():
    store = GameplayEventStore()
    _, _, owner = _setup(store)
    before = store.read_events()
    assert not owner.settle(_command(target_ref='missing')).committed
    assert not owner.settle(_command(rule_ref='rule:missing')).committed
    assert not owner.settle(_command(target_incarnation=2)).committed
    assert store.read_events() == before
    assert owner.settle(_command()).committed
    before = store.read_events()
    assert not owner.settle(_command(target_ref='other')).committed
    assert not owner.settle(_command(operation='revoke', original_fact_ref='fake', expected_revision=1,
        idempotency_key='revoke:wrong')).committed
    assert not owner.settle(_command(expected_revision=1, idempotency_key='overwrite')).committed
    assert store.read_events() == before


def test_despawn_between_evaluation_and_commit_prevents_fact_write(monkeypatch):
    store = GameplayEventStore()
    presence, _, owner = _setup(store)
    append = store.append_batch
    raced = False
    def race(batch):
        nonlocal raced
        if not raced:
            raced = True
            assert presence.despawn(CharacterDespawnRequest(world_ref=WORLD, character_ref=PROFILE,
                incarnation=1, expected_revision=1, idempotency_key='fact-race', reason='leave')).committed
        return append(batch)
    monkeypatch.setattr(store, 'append_batch', race)
    assert not owner.settle(_command()).committed


def test_self_consistent_batch_without_original_anchor_cut_is_not_owner_evidence():
    from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch

    source = GameplayEventStore()
    _, _, source_owner = _setup(source)
    issued = source_owner.settle(_command())
    original = source.get_event(issued.committed_event_ids[0])
    store = GameplayEventStore()
    _, _, owner = _setup(store)
    stream = owner.stream_id(WORLD, ACTOR)
    forged = build_multi_stream_atomic_event_batch(command_id=original.command_id,
        principal_ref='soul.fact_authority', expected_revisions={stream: 0},
        event_specs={stream: [(original.event_type, original.payload)]},
        event_visibility_policies={stream: ['authority_only']},
        idempotency_key='soul-fact:one', causation_id=original.causation_id,
        correlation_id=original.correlation_id,
        read_stream_revisions={stream: 0}, pinned_revisions={stream: 0})
    assert store.append_batch(forged).committed
    with pytest.raises(ValueError):
        owner.projection(_command())
    assert not owner.settle(_command()).committed


def test_fact_registration_and_request_are_closed_and_immutable():
    for change in [dict(expires_at=100), dict(principal_ref='admin'), dict(operations=('arbitrary_write',)),
                   dict(operations=('bind', 'bind')), dict(precedence=True), dict(precedence=-1)]:
        with pytest.raises(ValueError):
            _registration(**change)
    for change in [dict(allowed=True), dict(issuer_ref='admin'), dict(link_valid=True),
                   dict(actor_incarnation=True), dict(operation='revoke')]:
        with pytest.raises(ValueError):
            _command(**change)
    with pytest.raises(ValueError):
        _registration().version = 'changed'


def test_original_fact_receipt_corruption_rejected(monkeypatch):
    store = GameplayEventStore()
    _, _, owner = _setup(store)
    result = owner.settle(_command())
    assert result.committed
    get = store.get_by_idempotency
    def corrupt(principal, key):
        receipt = get(principal, key)
        if principal == 'soul.fact_authority' and receipt is not None:
            return receipt.model_copy(update={'global_sequence_range': (0, 0)})
        return receipt
    monkeypatch.setattr(store, 'get_by_idempotency', corrupt)
    assert not owner.settle(_command()).committed
    with pytest.raises(ValueError):
        owner.projection(_command())


def test_revoke_cannot_change_package_version_or_fact_policy():
    store = GameplayEventStore()
    registrations = (_registration(), _registration(version='2', kind='protection'))
    _, _, owner = _setup(store, registrations=registrations)
    result = owner.settle(_command())
    assert result.committed
    before = store.read_events()
    assert not owner.settle(_command(operation='revoke', version='2', expected_revision=1,
        original_fact_ref=result.committed_event_ids[0], idempotency_key='wrong-version')).committed
    assert store.read_events() == before


def test_projection_validates_full_receipt_and_original_batch(monkeypatch):
    store = GameplayEventStore()
    _, _, owner = _setup(store)
    result = owner.settle(_command())
    assert result.committed
    get = store.get_transaction
    event = store.get_event(result.committed_event_ids[0])
    def corrupt(transaction_id):
        batch = get(transaction_id)
        return batch.model_copy(update={'result_digest': 'corrupt'}) if transaction_id == event.transaction_id else batch
    monkeypatch.setattr(store, 'get_transaction', corrupt)
    with pytest.raises(ValueError):
        owner.projection(_command())
    assert not owner.settle(_command()).committed


def test_policy_snapshot_survives_redeployment_and_cannot_reinterpret_revoke():
    store = GameplayEventStore()
    _, anchors, owner = _setup(store)
    result = owner.settle(_command())
    assert result.committed
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload['registration'] == _registration().model_dump(mode='json')
    changed = _api().SoulFactAuthority(anchors=anchors,
        registrations=(_registration(operations=('curse', 'lift_curse')),))
    before = store.read_events()
    assert not changed.settle(_command(operation='revoke',
        original_fact_ref=event.event_id, expected_revision=1, idempotency_key='changed-policy')).committed
    assert store.read_events() == before
    assert changed.settle(_command()).zero_write


def test_distinct_registered_versions_have_independent_fact_lifecycles():
    store = GameplayEventStore()
    _, _, owner = _setup(store, registrations=(_registration(), _registration(version='2')))
    first = owner.settle(_command())
    assert first.committed
    second_command = _command(version='2', expected_revision=1, idempotency_key='version:two')
    assert owner.projection(second_command) == {}
    second = owner.settle(second_command)
    assert second.committed
    assert owner.projection(_command())['original_fact_ref'] == first.committed_event_ids[0]
    assert owner.projection(second_command)['original_fact_ref'] == second.committed_event_ids[0]


@pytest.mark.parametrize('change', [dict(operations=['arbitrary_write']), dict(kind='grant'),
    dict(version='other'), dict(precedence=999)])
def test_self_consistent_transaction_cannot_reinterpret_registration_snapshot(change):
    from app.gameplay.settlement_plan import build_multi_stream_atomic_event_batch

    source = GameplayEventStore()
    _, _, source_owner = _setup(source)
    issued = source_owner.settle(_command())
    original = source.get_event(issued.committed_event_ids[0])
    payload = dict(original.payload)
    payload['registration'] = dict(payload['registration']) | change
    store = GameplayEventStore()
    _, _, owner = _setup(store)
    stream = owner.stream_id(WORLD, ACTOR)
    batch = build_multi_stream_atomic_event_batch(command_id=original.command_id,
        principal_ref='soul.fact_authority', expected_revisions={stream: 0},
        event_specs={stream: [(original.event_type, payload)]},
        event_visibility_policies={stream: ['authority_only']},
        idempotency_key='soul-fact:one', causation_id=original.causation_id,
        correlation_id=original.correlation_id,
        read_stream_revisions={stream: 0}, pinned_revisions={stream: 0})
    assert store.append_batch(batch).committed
    with pytest.raises(ValueError):
        owner.projection(_command())
    assert not owner.settle(_command()).committed


