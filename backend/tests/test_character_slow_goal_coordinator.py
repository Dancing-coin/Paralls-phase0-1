from types import SimpleNamespace

import pytest

from app.character_agent.gateway.goal_proposal import GoalProposalContext
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.services.cognition_coordinator import CharacterCognitionCoordinator
from app.config import settings
from test_character_slow_goal_contract import proposal_context


class FakeAdmissions:
    def __init__(self, entry):
        self.store = object()
        self.entry = entry
        self.progress = None
        self.calls = []

    def _owner(self):
        return None

    def read(self, key):
        return self.entry if key == self.entry.child_key else None

    def read_progress(self, key, **kwargs):
        return self.progress

    def _validate_source(self, entry):
        return None

    @staticmethod
    def _validate_contract_source_pins(frame, source_pins):
        return None

    def advance_progress(self, **kwargs):
        self.calls.append(kwargs)
        self.progress = SimpleNamespace(
            stage=kwargs['stage'], status=kwargs['status'],
            request_json=kwargs.get('request_json'), frame=kwargs['frame'],
        )
        return self.progress


def _coordinator():
    context = GoalProposalContext.model_validate(proposal_context())
    entry = SimpleNamespace(
        child_key='child:proposal', actor_id='char_a', source_kind='goal_proposal_trigger',
        payload={'context': context.model_dump(mode='json'), 'evidence_refs': ['outcome:1']},
        source_pins={}, producer_ts=10, expires_at=30,
    )
    admissions = FakeAdmissions(entry)
    gateway = CharacterModelGateway()
    runtime = SimpleNamespace(
        _session_store=admissions.store,
        _l3=SimpleNamespace(_gateway=gateway),
        activation_is_current=lambda lock, token: (lock, token) == ('lock', 'token'),
        _capture_cognition_pin=lambda actor_id: {'goal_revision': 2},
    )
    return CharacterCognitionCoordinator(runtime=runtime, admissions=admissions), admissions


def test_prepare_goal_proposal_freezes_json_request_and_progress(monkeypatch):
    monkeypatch.setattr(settings, 'character_model_provider_kind', 'deepseek')
    coordinator, admissions = _coordinator()
    result = coordinator.prepare_goal_proposal(
        'child:proposal', activation=SimpleNamespace(actor_id='char_a', lock_ref='lock', token='token'), now=11,
    )
    assert result.status == 'provider_pending'
    assert isinstance(result.request_json, str)
    assert admissions.calls[0]['request_json'] == result.request_json
    assert admissions.calls[0]['frame']['stage'] == 'goal_proposal'


def test_prepare_goal_proposal_exact_retry_reuses_original_request(monkeypatch):
    monkeypatch.setattr(settings, 'character_model_provider_kind', 'deepseek')
    coordinator, admissions = _coordinator()
    activation = SimpleNamespace(actor_id='char_a', lock_ref='lock', token='token')
    first = coordinator.prepare_goal_proposal('child:proposal', activation=activation, now=11)
    second = coordinator.prepare_goal_proposal('child:proposal', activation=activation, now=12)
    assert second.request_json == first.request_json
    assert len(admissions.calls) == 1


def test_prepare_goal_proposal_retry_returns_frozen_request_without_rerouting(monkeypatch):
    monkeypatch.setattr(settings, 'character_model_provider_kind', 'deepseek')
    coordinator, admissions = _coordinator()
    activation = SimpleNamespace(actor_id='char_a', lock_ref='lock', token='token')
    first = coordinator.prepare_goal_proposal('child:proposal', activation=activation, now=11)
    original_gateway = coordinator.runtime._l3._gateway

    class ReroutedGateway:
        def prepare_run_request(self, **kwargs):
            raise AssertionError('a retry must use the frozen request')

    coordinator.runtime._l3._gateway = ReroutedGateway()
    second = coordinator.prepare_goal_proposal('child:proposal', activation=activation, now=12)
    assert second.request_json == first.request_json
    assert len(admissions.calls) == 1
    coordinator.runtime._l3._gateway = original_gateway


def test_prepare_goal_proposal_rejects_non_goal_source_without_write():
    coordinator, admissions = _coordinator()
    admissions.entry.source_kind = 'run_background_cognition_tick'
    with pytest.raises(ValueError, match='goal_proposal_source_required'):
        coordinator.prepare_goal_proposal(
            'child:proposal', activation=SimpleNamespace(actor_id='char_a', lock_ref='lock', token='token'), now=11,
        )
    assert admissions.calls == []
