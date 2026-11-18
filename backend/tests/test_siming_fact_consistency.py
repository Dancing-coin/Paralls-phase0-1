import pytest

from app.services.siming_fact_core import SimingFactCore
from test_siming_fact_locking import event


@pytest.mark.parametrize(('change', 'reason'), [
    ({'value': 'char_b'}, 'fact_value_conflict'),
    ({'world_anchor_id': 'other'}, 'fact_metadata_conflict'),
    ({'fact_category': 'case'}, 'fact_metadata_conflict'),
])
def test_siming_rejects_rewriting_locked_fact(change, reason):
    core = SimingFactCore()
    assert core.evaluate([event(world_anchor_id='body', state_key='culprit')]).accepted
    args = dict(ts=11, world_anchor_id='body', state_key='culprit')
    args.update(change)
    result = core.evaluate([event(**args)])
    assert not result.accepted and result.veto_reason == reason
    assert result.conflict_refs


def test_siming_detects_anchor_conflict_but_allows_different_property():
    core = SimingFactCore()
    assert core.evaluate([event(world_anchor_id='body', state_key='culprit')]).accepted
    result = core.evaluate([event(fact_id='other', value='char_b', ts=11,
                                  world_anchor_id='body', state_key='culprit')])
    assert not result.accepted and result.veto_reason == 'world_anchor_conflict'
    assert core.evaluate([event(fact_id='other', value='red', ts=12,
                                world_anchor_id='body', state_key='color')]).accepted


@pytest.mark.parametrize(('refs', 'reason'), [
    ({'evidence_refs': ['missing']}, 'unknown_evidence_reference'),
    ({'source_event_refs': ['missing']}, 'broken_fact_source_chain'),
    ({'evidence_refs': 'fact:culprit'}, 'invalid_fact_references'),
    ({'evidence_refs': ['other']}, 'self_fact_reference'),
    ({'source_event_refs': ['write:other:11']}, 'self_fact_reference'),
])
def test_siming_rejects_bad_evidence_and_sources(refs, reason):
    core = SimingFactCore()
    assert core.evaluate([event()]).accepted
    result = core.evaluate([event(fact_id='other', ts=11, **refs)])
    assert not result.accepted and result.veto_reason == reason
    assert 'other' not in core.snapshot_for(event().authority_event).facts


def test_siming_evidence_chain_is_stored_and_cannot_point_into_future():
    core = SimingFactCore()
    assert core.evaluate([event()]).accepted
    assert core.evaluate([event(fact_id='other', ts=11, evidence_refs=['fact:culprit'],
                                source_event_refs=['write:fact:culprit:10'])]).accepted
    fact = core.snapshot_for(event().authority_event).facts['other']
    assert fact.evidence_refs == ['fact:culprit']
    assert fact.source_event_refs == ['write:fact:culprit:10']
    result = core.evaluate([event(fact_id='third', ts=9, evidence_refs=['other'])])
    assert not result.accepted and result.veto_reason == 'fact_time_reversal'


def test_siming_deduction_requires_evidence_and_never_adds_fact():
    core = SimingFactCore()
    assert core.evaluate([event()]).accepted
    deduction = event('deduce', fact_id='conclusion', ts=11)
    deduction.payload.pop('fact_value')
    assert core.evaluate([deduction]).veto_reason == 'deduction_requires_evidence'
    deduction.payload['evidence_refs'] = ['fact:culprit']
    assert core.evaluate([deduction]).accepted
    assert set(core.snapshot_for(event().authority_event).facts) == {'fact:culprit'}


def test_siming_fact_rejects_source_prefix_impersonation():
    observation = event()
    observation.authority_event.source.system = 'siming_fake'
    assert SimingFactCore().evaluate([observation]).veto_reason == 'invalid_fact_source'

def test_siming_t3_rejects_new_write_envelope_even_for_same_value():
    core = SimingFactCore()
    assert core.evaluate([event()]).accepted
    for index in (1, 2, 3):
        assert core.evaluate([event('advance_phase', ts=10+index, fact_phase=f'T{index}')]).accepted
    result = core.evaluate([event(ts=20)])
    assert not result.accepted and result.veto_reason == 'fact_frozen'


def test_siming_rejects_missing_fact_identity_in_explicit_value_declaration():
    observation = event()
    observation.payload.pop('fact_operation')
    observation.payload.pop('fact_id')
    assert SimingFactCore().evaluate([observation]).veto_reason == 'invalid_fact_payload'


def test_siming_fact_source_identity_cannot_be_reused_with_different_envelope():
    core = SimingFactCore()
    first = event()
    assert core.evaluate([first]).accepted
    changed = event()
    changed.authority_event.correlation_id = 'other'
    assert core.evaluate([changed]).veto_reason == 'fact_source_identity_conflict'


def test_siming_bool_and_integer_are_different_fact_values():
    core = SimingFactCore()
    assert core.evaluate([event(value=True)]).accepted
    assert core.evaluate([event(value=1, ts=11)]).veto_reason == 'fact_value_conflict'

def test_siming_accepted_owner_observation_can_supply_evidence_and_source():
    from app.models.siming_runtime_state import ObservedSimingEvent
    from test_siming_fact_core import make_event
    observed = ObservedSimingEvent.from_authority_event(make_event(established_fact_id='owner:evidence'))
    core = SimingFactCore()
    assert core.evaluate([observed]).accepted
    result = core.evaluate([event(ts=301, evidence_refs=['owner:evidence'],
                                  source_event_refs=[observed.source_event_id])])
    assert result.accepted, result.veto_reason
    assert core.evaluate([event(fact_id='later', ts=302, evidence_refs=[observed.source_event_id])]).accepted
