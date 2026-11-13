import pytest
from app.models.world_result import ConstraintStateResult
from app.services.esm_service import ESMService
from app.gameplay.event_store import GameplayEventStore
from app.services.siming_environment_protocol import SimingEnvironmentProtocol
from test_siming_esm_protocol_stub import _make_siming_env_event


def test_siming_environment_protocol_preserves_decision_and_returns_both_results():
    source = _make_siming_env_event()
    source.payload.update(candidate_ref='candidate:1', decision_ref='decision:1')
    request, resolution, state = SimingEnvironmentProtocol().resolve(
        source, esm=ESMService(store=GameplayEventStore(), learning_disclosure_scopes={}))
    assert request.request_id == source.event_id
    assert request.candidate_ref == 'candidate:1'
    assert request.decision_ref == 'decision:1'
    assert request.ttl == source.ttl
    assert resolution.resolution_status == 'accepted'
    assert state.current_state == 'alerted'
    assert state.request_ref == request.request_id


def test_siming_environment_protocol_rejection_keeps_constraint_and_has_no_state():
    source = _make_siming_env_event()
    source.payload['requested_change_type'] = 'teleport_world'
    request, resolution, state = SimingEnvironmentProtocol().resolve(
        source, esm=ESMService(store=GameplayEventStore(), learning_disclosure_scopes={}))
    assert isinstance(resolution, ConstraintStateResult)
    assert resolution.constraint_code == 'unsupported_change_type'
    assert state is None


@pytest.mark.parametrize('field,value', [('request_ref','forged'), ('room_id','elsewhere'),
    ('result_type','constraint_state_result'), ('correlation_id','forged'), ('target_environment_id','elsewhere'), ('producer_ts',0)])
def test_siming_environment_protocol_rejects_unrelated_results(field, value):
    esm = ESMService(store=GameplayEventStore(), learning_disclosure_scopes={})
    class Forged:
        def resolve_environment_request(self, request):
            resolution, state = esm.resolve_environment_request(request)
            return resolution, state.model_copy(update={field:value})
    _, resolution, state = SimingEnvironmentProtocol().resolve(_make_siming_env_event(), esm=Forged())
    assert isinstance(resolution, ConstraintStateResult)
    assert resolution.constraint_code == 'invalid_environment_result'
    assert state is None


@pytest.mark.parametrize('mode', ['timeout', 'missing_state', 'missing_target', 'malformed_target', 'expired'])
def test_siming_environment_protocol_fails_closed_without_escalation(mode):
    calls=[]
    source=_make_siming_env_event()
    if mode == 'missing_target':
        source.payload.pop('target_environment_id')
    if mode == 'malformed_target':
        source.payload['target_environment_id'] = {'invalid': True}
    if mode == 'expired':
        source=source.model_copy(update={'ttl':0})
    esm=ESMService(store=GameplayEventStore(), learning_disclosure_scopes={})
    class Broken:
        def resolve_environment_request(self, request):
            calls.append(request)
            if mode == 'timeout':
                raise TimeoutError('offline')
            resolution, state=esm.resolve_environment_request(request)
            return resolution, None if mode == 'missing_state' else state
    _, resolution, state=SimingEnvironmentProtocol().resolve(source,esm=Broken())
    assert isinstance(resolution,ConstraintStateResult)
    assert resolution.settlement_status=='rejected'
    assert state is None
    if mode in {'missing_target','malformed_target','expired'}:
        assert calls==[]


def test_siming_environment_handler_publishes_validated_resolution_and_state(monkeypatch):
    from app import main
    emitted, applied = [], []
    monkeypatch.setattr(main, 'esm_service', ESMService(store=GameplayEventStore(), learning_disclosure_scopes={}), raising=False)
    monkeypatch.setattr(main, '_publish_world_result_authority_event', lambda result, **kw: emitted.append((result, kw)) or [])
    from types import SimpleNamespace
    monkeypatch.setattr(main, 'l1_occupancy_service', SimpleNamespace(apply_environment_result=applied.append), raising=False)
    main._handle_siming_environment_request(_make_siming_env_event())
    assert len(emitted) == 2
    assert all(kw['drain_frontend'] is False for _, kw in emitted)
    assert emitted[1][0].result_type == 'environment_state_result'
    assert applied == [emitted[1][0]]


def test_siming_environment_constraint_reenters_runtime_without_catalyst():
    from app.models.siming_event import SimingInput
    from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
    from app.services.siming_runtime import SimingRuntime
    source=_make_siming_env_event()
    source.payload['requested_change_type']='unsupported'
    request, resolution, _ = SimingEnvironmentProtocol().resolve(source,
        esm=ESMService(store=GameplayEventStore(), learning_disclosure_scopes={}))
    event=Phase0AuthorityEventAdapter().world_result_event(resolution,source_event=request)
    result=SimingRuntime().tick([SimingInput(input_type='constraint_state_event',source_event=event)])
    assert any(audit.status=='esm_rejected' for audit in result.audit_records)
    assert not any(item.output_type=='dispatch_intent' for item in result.outputs)


@pytest.mark.parametrize('now_ts,code', [(None, 'ttl_clock_unavailable'), (111, 'expired_ttl')])
def test_siming_environment_positive_ttl_requires_valid_same_domain_clock(now_ts, code):
    source = _make_siming_env_event().model_copy(update={'ttl': 10})
    class Uncalled:
        def resolve_environment_request(self, request):
            pytest.fail('expired or unclocked request must not reach ESM')
    _, resolution, state = SimingEnvironmentProtocol().resolve(source, esm=Uncalled(), now_ts=now_ts)
    assert resolution.constraint_code == code
    assert state is None
