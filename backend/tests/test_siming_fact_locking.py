import pytest

from app.models.siming_runtime_state import ObservedSimingEvent
from app.services.siming_fact_core import SimingFactCore
from test_siming_fact_core import make_event


def event(operation='write', fact_id='fact:culprit', value='char_a', ts=10, **payload):
    data = {'fact_operation': operation}
    if operation != 'advance_phase':
        data.update(fact_id=fact_id, fact_value=value)
    data.update(payload)
    source = make_event().model_copy(update={
        'event_id': f'{operation}:{fact_id}:{ts}', 'event_type': 'world_fact_event',
        'producer_ts': ts, 'payload': data,
        'source': make_event().source.model_copy(update={'layer': 'L2', 'system': 'siming.fact_core'}),
    })
    return ObservedSimingEvent.from_authority_event(source)


def advance(core, phase, ts):
    return core.evaluate([event('advance_phase', ts=ts, fact_phase=phase)])


@pytest.mark.parametrize('phase', ['T2', 'T3'])
def test_siming_lock_stops_new_facts_and_allows_reveal(phase):
    core = SimingFactCore()
    assert core.evaluate([event()]).accepted
    for index in range(1, int(phase[1]) + 1):
        assert advance(core, f'T{index}', 10 + index).accepted
    result = core.evaluate([event(fact_id='fact:new', ts=20)])
    assert not result.accepted
    assert result.veto_reason == 'fact_set_locked'
    assert result.phase == phase
    reveal = event('reveal', ts=21)
    reveal.payload.pop('fact_value')
    assert core.evaluate([reveal]).accepted
    assert core.evaluate([event(ts=10)]).accepted  # exact replay survives later locks


@pytest.mark.parametrize('phase', ['T2', 'T-1', 'unlocked'])
def test_siming_lock_rejects_invalid_transition_without_state_change(phase):
    core = SimingFactCore()
    before = core.snapshot_for(event().authority_event)
    result = advance(core, phase, 11)
    assert not result.accepted
    assert result.veto_reason == 'invalid_fact_phase_transition'
    assert core.snapshot_for(event().authority_event) == before


def test_siming_lock_cannot_roll_back_after_progression():
    core = SimingFactCore()
    assert advance(core, 'T1', 11).accepted
    assert not advance(core, 'T0', 12).accepted


def test_siming_lock_batch_is_atomic_and_planning_is_pure():
    core = SimingFactCore()
    plan = core.plan_evaluate([event()])
    assert plan.accepted and plan.states
    assert core.snapshot_for(event().authority_event) is None
    core.install_snapshot(plan.states[0])
    before = core.snapshot_for(event().authority_event)
    bad = core.evaluate([event(fact_id='fact:other', ts=11), event('advance_phase', ts=12, fact_phase='T3')])
    assert not bad.accepted
    assert core.snapshot_for(event().authority_event) == before


def test_siming_lock_scopes_are_independent_and_snapshots_are_detached():
    core = SimingFactCore()
    assert core.evaluate([event()]).accepted
    assert advance(core, 'T1', 11).accepted
    assert advance(core, 'T2', 12).accepted
    other = event(fact_id='fact:other', ts=13)
    other.room_id = 'another'
    other.authority_event = other.authority_event.model_copy(update={'room_id': 'another'})
    assert core.evaluate([other]).accepted
    snapshot = core.snapshot_for(event().authority_event)
    snapshot.facts.clear()
    assert core.snapshot_for(event().authority_event).facts


def test_siming_lock_no_new_foundation_after_t0():
    core = SimingFactCore()
    assert advance(core, 'T1', 11).accepted
    result = core.evaluate([event(ts=12, fact_category='foundation')])
    assert not result.accepted and result.veto_reason == 'fact_category_locked'


def test_siming_lock_observes_owner_changes_after_t3_without_rewriting_case_truth():
    core = SimingFactCore()
    for index in range(1, 4):
        assert advance(core, f'T{index}', index).accepted
    observed = ObservedSimingEvent.from_authority_event(make_event())
    assert core.evaluate([observed]).accepted
    assert core.snapshot_for(observed.authority_event).phase == 'T3'
