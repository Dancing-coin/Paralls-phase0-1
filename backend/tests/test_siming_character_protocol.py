import pytest

from app.models.siming_event import SimingInput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_feasibility import SimingFeasibilityResult
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_policy import SimingPolicyResult
from app.services.siming_runtime import SimingRuntime
from test_siming_llm_runtime import make_candidate, make_visual_fact_event


class Receiver:
    def supports_actor(self, actor):
        return actor == 'char_b'


@pytest.mark.parametrize('band', ['impulse', 'opportunity', 'fact_reveal'])
def test_siming_character_protocol_preserves_band_and_evidence(band):
    candidate = make_candidate(proposed_band=band, target_environment_id=None)
    runtime = SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([candidate]))
    source = make_visual_fact_event()
    result = runtime.tick([SimingInput(input_type='visual_fact_event', source_event=source)])
    dispatch = next(item for item in result.outputs if item.output_type == 'dispatch_intent')
    event = SimingEventProducer(InMemoryAuthorityEventBus()).materialize_outputs([dispatch])[0]
    delivery = SimingCharacterDispatchAdapter(runtime=Receiver()).prepare_deliveries(event)
    assert len(delivery.delivery_inputs) == 1
    item = delivery.delivery_inputs[0]
    assert item.band == band
    assert item.evidence_refs == candidate.established_fact_ids
    assert item.causation_id == source.event_id
    assert item.correlation_id == source.correlation_id
    assert not delivery.commands_by_actor


@pytest.mark.parametrize('reject_stage', ['fact', 'policy', 'feasibility'])
def test_siming_character_protocol_filters_legacy_environment_attention(reject_stage):
    calls = []

    class Policy:
        def evaluate(self, candidate, *, snapshot):
            calls.append('policy')
            return SimingPolicyResult(reject_stage != 'policy', ['test_policy'])

    class Feasibility:
        def evaluate(self, candidate):
            calls.append('feasibility')
            return SimingFeasibilityResult(reject_stage != 'feasibility', 'character_input_path', ['test_feasibility'])

    event = make_visual_fact_event().model_copy(update={
        'event_type': 'esm_result_event',
        'payload': {'result_type': 'environment_state_result', 'target_environment_id': 'env_lamp',
                    'locked_fact_conflict': reject_stage == 'fact'},
    })
    result = SimingRuntime(policy=Policy(), feasibility=Feasibility(),
                           actor_roster_resolver=lambda _: ["actor_test"]).tick([
        SimingInput(input_type='esm_result_event', source_event=event),
    ])
    assert not any(item.output_type == 'dispatch_intent' for item in result.outputs)
    assert calls == ([] if reject_stage == 'fact' else ['policy'] if reject_stage == 'policy' else ['policy', 'feasibility'])
    assert any(item.status in {'no_action', 'policy_rejected', 'feasibility_rejected'} for item in result.audit_records)


def test_siming_character_protocol_rule_cannot_grant_unknown_actor_eligibility():
    event = make_visual_fact_event().model_copy(update={
        'event_type': 'conversation_resolution_event',
        'payload': {'candidate_actor_ids': ['unregistered_actor']},
    })
    result = SimingRuntime().tick([SimingInput(input_type='conversation_resolution_event', source_event=event)])
    assert not any(item.output_type == 'dispatch_intent' for item in result.outputs)
    assert any('actor_not_eligible' in item.reason for item in result.audit_records)
