import copy
import json

import pytest

from app.services.dialogue_service import DialogueService
from test_dialogue_completion_lifecycle import coordinator, begin, complete


def test_player_reply_context_addresses_actual_recipient():
    from app.services.character_service import CharacterService
    from test_dialogue_completion_lifecycle import event

    context = json.loads(CharacterService().prepare_dialogue(event()))['context']
    assert context['actor_id'] == 'char_a'
    assert context['event']['target_actor_id'] == 'char_c'


def dialogue_stage(assisted=False):
    owner = coordinator()
    if assisted:
        from test_cognition_completion_revision import ModelGateway
        owner.runtime.set_control_mode('char_a', 'player_priority_assisted')
        owner.runtime._l2._gateway = owner.runtime._l3._gateway = ModelGateway()
    advance = begin(owner)
    requests = []
    while advance.status == 'pending' and advance.job.stage == 'cognition':
        requests.append(json.loads(advance.job.request_json))
        advance, _ = complete(owner, advance)
    assert advance.status == 'pending' and advance.job.stage == 'dialogue_generation'
    return owner, advance, requests


@pytest.mark.parametrize('assisted', [False, True])
def test_actual_dialogue_fallback_keeps_original_l2_l3_policy_turn_and_recall_budget(assisted):
    owner, advance, cognition = dialogue_stage(assisted)
    try:
        context = json.loads(advance.job.request_json)['context']
        assert context['cognition_policy'] == cognition[0]['context']['cognition_policy']
        assert context['capability_envelope'] == cognition[0]['context']['capability_envelope']
        assert context['turn_id'] == cognition[0]['context']['turn_id']
        for request in cognition:
            assert request['context']['cognition_policy'] == context['cognition_policy']
        assert context['memory_recall']['cognition_policy_digest'] == context['cognition_policy']['policy_digest']
        assert context['event']['target_actor_id'] == 'char_c'
    finally:
        owner.close()


@pytest.mark.parametrize('defect', ['actor', 'turn', 'policy_digest', 'missing_pair', 'missing_digest', 'missing_envelope_digest'])
def test_dialogue_rejects_cross_actor_turn_or_tampered_inherited_contract(defect):
    owner, _, cognition = dialogue_stage()
    try:
        original = cognition[0]['context']
        inherited = copy.deepcopy({key: original[key] for key in
            ('capability_envelope', 'cognition_policy', 'turn_id')})
        actor = 'char_a'
        if defect == 'actor':
            actor = 'char_b'
        elif defect == 'turn':
            inherited['turn_id'] = 'different-turn'
        elif defect == 'policy_digest':
            inherited['cognition_policy']['dialogue']['max_tokens'] = 9000
        elif defect == 'missing_pair':
            del inherited['capability_envelope']
        elif defect == 'missing_digest':
            del inherited['cognition_policy']['policy_digest']
        else:
            del inherited['capability_envelope']['envelope_digest']
        with pytest.raises(ValueError):
            DialogueService().prepare_dialogue(actor_id=actor, target_actor_id='char_c',
                content='hello', cognition_context=inherited)
    finally:
        owner.close()


def test_agent_fallback_does_not_inherit_recipient_private_contract():
    from test_dialogue_review_fixes import begin_agent

    owner = coordinator()
    try:
        advance = begin_agent(owner)
        while advance.job.stage == 'cognition':
            advance, _ = complete(owner, advance)
        context = json.loads(advance.job.request_json)['context']
        assert context['actor_id'] == 'char_b'
        # Own-speaker policy admission is a separate remaining production lane.
        assert 'cognition_policy' not in context
        assert 'capability_envelope' not in context
    finally:
        owner.close()


def test_durable_suggestion_request_reuses_frozen_turn_contract(tmp_path):
    from app.models.character_agent_runtime import CharacterInterpretation
    from test_durable_cognition_shared_contract import _pending

    runtime, _, _, _, _, pending = _pending(tmp_path)
    try:
        interpretation = CharacterInterpretation(actor_id='char_a', interpreted_summary='watch',
            interpretation_type='observation', salience_score=.5, ambiguity_level='low',
            risk_level='low', opportunity_level='low')
        prepared, _ = runtime._freeze_suggestion_request('char_a', dict(pending.frame,
            interpretation=interpretation.model_dump(mode='json')))
        actual = json.loads(prepared.request_json)['context']
        original = json.loads(pending.request_json)['context']
        for key in ('capability_envelope', 'cognition_policy', 'turn_id'):
            assert actual[key] == original[key]
    finally:
        runtime.close()
