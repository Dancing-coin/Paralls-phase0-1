"""Frozen stage contracts must retain typed content and exact identity."""
from copy import deepcopy

import pytest

from app.character_agent.cognition.capability_envelope import CapabilityEnvelope
from app.character_agent.cognition.cognition_policy import CognitionPolicy
from app.character_agent.services.cognition_frame import (
    freeze_fields, validate_cognition_contract, validate_frame,
)


def contract():
    envelope = CapabilityEnvelope.compile(actor_id='char_a', turn_id='turn:a',
        source_refs=['event:a'], revision_pins={'policy_revision': 'policy:1'})
    policy = CognitionPolicy.resolve(envelope=envelope)
    return dict(actor_id='char_a', turn_id='turn:a',
        capability_envelope=envelope.model_dump(mode='json'),
        cognition_policy=policy.model_dump(mode='json'))


def test_valid_typed_contract_and_legacy_frame_are_accepted():
    frame = contract()
    frame['revision_pins'] = dict(frame['cognition_policy']['revision_pins'])
    frame['source_event_ref'] = 'event:a'
    validate_cognition_contract(frame)
    validate_cognition_contract({'actor_id': 'char_a'})


@pytest.mark.parametrize('defect', ['envelope_body', 'policy_body', 'actor', 'turn',
    'policy_pins', 'frame_pins', 'missing_turn', 'source'])
def test_stage_rejects_changed_content_or_inconsistent_contract(defect):
    frame = deepcopy(contract())
    if defect == 'envelope_body':
        frame['capability_envelope']['allowed_action_families'] = ['invented']
    elif defect == 'policy_body':
        frame['cognition_policy']['dialogue']['max_tokens'] += 1
    elif defect in {'actor', 'turn', 'policy_pins'}:
        raw = frame['cognition_policy']
        if defect == 'policy_pins':
            raw['revision_pins']['policy_revision'] = 'other'
        else:
            raw[defect + '_id'] = 'other'
        raw.pop('policy_digest')
        frame['cognition_policy'] = CognitionPolicy.model_validate(raw).model_dump(mode='json')
    elif defect == 'frame_pins':
        frame['revision_pins'] = {'policy_revision': 'other'}
    elif defect == 'missing_turn':
        frame.pop('turn_id')
    else:
        frame['source_event_ref'] = 'event:other'
    with pytest.raises(ValueError):
        validate_cognition_contract(frame)


def test_foreign_contract_cannot_be_validated_without_large_field_references():
    with pytest.raises(ValueError):
        validate_frame(None, contract(), actor_id='char_b', child_key='child')


def test_invalid_contract_is_rejected_before_any_frozen_receipt_write():
    class Store:
        def save_receipt(self, *args, **kwargs):
            pytest.fail('invalid contract wrote a receipt')

    frame = contract()
    frame['cognition_policy']['dialogue']['max_tokens'] += 1
    with pytest.raises(ValueError):
        freeze_fields(Store(), frame, actor_id='char_a', child_key='child',
            origin_stage='l2', fields={'context': {}})


@pytest.mark.parametrize('field', ['envelope_digest', 'policy_digest',
    'capability_envelope', 'cognition_policy'])
def test_partial_or_explicitly_null_contract_is_not_legacy(field):
    with pytest.raises(ValueError):
        validate_cognition_contract({'actor_id': 'char_a', field: None})
