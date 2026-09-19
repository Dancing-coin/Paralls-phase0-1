import pytest
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
from app.population_continuity.activation_policy import ActivationPolicy


def setup(path):
    from app.character_agent.services.scheduled_cognition import ScheduledCognitionSource
    rt = CharacterAgentRuntime(storage_root=path)
    policy = ActivationPolicy()
    source = ScheduledCognitionSource(runtime=rt, policy=policy)
    admissions = CharacterCognitionAdmissionService(store=rt._session_store, assert_owner=rt._assert_cognition_owner,
        validate_source=source.validate, activation_is_current=rt.activation_is_current)
    source.admissions = admissions
    rt.set_background_cognition_enabled(True)
    rt.set_background_mode('char_a', 'active')
    return rt, source


def test_original_session_source_reopens_without_renewing_admission(tmp_path, monkeypatch):
    rt, source = setup(tmp_path)
    monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_a'])
    original = rt._session_store.append_event('char_a', 'character_perceived_event', 123, {'summary': 'light'})
    first = source.admit(source_actor='char_a', producer_ts=123, now=10.)
    assert len(first) == 1 and first[0].payload == {}
    assert first[0].source_event == original
    rt.close()
    rt, source = setup(tmp_path)
    monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_a'])
    try:
        rt._session_store.append_event('char_a', 'character_perceived_event', 124, {'summary': 'later'})
        rt.set_background_cognition_enabled(False)
        monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_b'])
        before = rt._session_store._connection.total_changes
        assert source.admit(source_actor='char_a', producer_ts=123, now=50., source_event=original) == first
        assert rt._session_store._connection.total_changes == before
        source.validate(first[0])
        altered = first[0].model_copy(update={'source_event': {**original, 'payload': {'summary': 'forged'}}})
        with pytest.raises(ValueError, match='scheduled_source_invalid'): source.validate(altered)
    finally: rt.close()


def test_gate_and_missing_original_source_do_not_create_jobs(tmp_path, monkeypatch):
    rt, source = setup(tmp_path)
    monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_a'])
    try:
        assert source.admit(source_actor='char_a', producer_ts=123, now=10.) == ()
        rt._session_store.append_event('char_a', 'character_perceived_event', 123, {})
        rt.set_background_cognition_enabled(False)
        assert source.admit(source_actor='char_a', producer_ts=123, now=10.) == ()
        rt.set_background_cognition_enabled(True)
        rt.set_background_mode('char_a', 'off')
        assert source.admit(source_actor='char_a', producer_ts=123, now=10.) == ()
    finally: rt.close()


@pytest.mark.parametrize('eligible,budget,supported,active', [(True,4,True,True), (False,4,True,False), (True,0,True,False), (True,4,False,False)])
def test_scheduled_policy_preserves_original_eligibility(eligible,budget,supported,active):
    decision = ActivationPolicy().evaluate_scheduled_background(actor_id='char_a', eligible=eligible,
        budget=budget, supported_actor=supported)
    assert (decision.state == 'active') == active


def test_scheduled_batch_failure_rolls_back_all_child_admissions(tmp_path, monkeypatch):
    rt, source = setup(tmp_path)
    rt.set_background_mode('char_b', 'active')
    monkeypatch.setattr(rt, 'get_schedulable_actor_ids', lambda: ['char_a', 'char_b'])
    event = rt._session_store.append_event('char_a', 'character_perceived_event', 123, {})
    original = source.admissions.admit
    def fail_second(**kwargs):
        if kwargs['actor_id'] == 'char_b': raise OSError('second child')
        return original(**kwargs)
    monkeypatch.setattr(source.admissions, 'admit', fail_second)
    try:
        with pytest.raises(OSError, match='second child'):
            source.admit(source_actor='char_a', producer_ts=123, now=10.)
        assert source.admissions.list_pending() == ()
        assert rt._session_store.read_receipt('char_a', kind='scheduled_cognition', key=event['event_id']) is None
        monkeypatch.setattr(source.admissions, 'admit', original)
        assert len(source.admit(source_actor='char_a', producer_ts=123, now=11.)) == 2
    finally: rt.close()
