import pytest

from app.population_continuity.activation_policy import ActivationPolicy
from test_cognition_completion_revision import runtime, source_args


@pytest.mark.parametrize('band', ['impulse', 'opportunity', 'fact_reveal'])
def test_siming_high_level_input_has_explicit_activation_policy(band):
    delivery = source_args(runtime(), 'ingest_siming_output')['payload'].model_copy(update={'band': band})
    decision = ActivationPolicy().evaluate_siming_delivery(actor_id='char_a', delivery=delivery,
        budget=1, supported_actor=True, stale_revision=False)
    assert decision.state == 'active'
    assert decision.reason == 'siming_high_level_input'
    assert decision.requires_activation_lock and decision.load_private_memory


@pytest.mark.parametrize('change,reason', [
    ({'supported_actor': False}, 'unsupported_actor'),
    ({'stale_revision': True}, 'stale_revision'),
    ({'budget': 0}, 'activation_budget_exhausted'),
    ({'actor_id': 'char_b'}, 'siming_target_mismatch'),
])
def test_siming_policy_rejects_invalid_target_or_activation_fence(change, reason):
    args = dict(actor_id='char_a', delivery=source_args(runtime(), 'ingest_siming_output')['payload'],
        budget=1, supported_actor=True, stale_revision=False)
    args.update(change)
    decision = ActivationPolicy().evaluate_siming_delivery(**args)
    assert decision.state == 'requeue' and decision.reason == reason
    assert not decision.requires_activation_lock and not decision.load_private_memory
