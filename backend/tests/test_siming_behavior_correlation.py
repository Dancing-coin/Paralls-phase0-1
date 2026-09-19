import pytest
from app import main
from app.config import Settings
from app.models.siming_event import SimingInput
from test_siming_heavenly_runtime_composition import _authority_destruction_event


@pytest.mark.parametrize('reopen', [False, True])
@pytest.mark.parametrize('offset', [2, -1])
def test_later_same_correlation_preserves_first_durable_behavior_audit(tmp_path, reopen, offset):
    settings = Settings(siming_heavenly_mode='off', heavenly_graph_path=str(tmp_path / 'graph.db'))
    state = main.build_runtime_state(settings)
    try:
        event = _authority_destruction_event()
        first = state.siming_runtime.plan_initial(SimingInput(input_type='esm_result_event', source_event=event))
        audits = [batch for batch in first.effects.batches if batch.idempotency_key.startswith('siming-behavior-turn:')]
        assert len(audits) == 1
        state.heavenly_graph.write_batch(audits[0])
        if reopen:
            state.close()
            state = main.build_runtime_state(settings)
        later = event.model_copy(update={'event_id': event.event_id+':object', 'producer_ts': event.producer_ts+offset,
            'payload': {**event.payload, 'result_type': 'object_state_result'}})
        second = state.siming_runtime.plan_initial(SimingInput(input_type='esm_result_event', source_event=later))
        assert not any(batch.idempotency_key == audits[0].idempotency_key for batch in second.effects.batches)
        assert second.after.siming_input.source_event == later
        assert state.heavenly_graph.write_batch(audits[0]).replayed
    finally:
        state.close()

def test_behavior_receipt_without_original_anchor_is_not_accepted(tmp_path, monkeypatch):
    state = main.build_runtime_state(Settings(siming_heavenly_mode='off', heavenly_graph_path=str(tmp_path / 'graph.db')))
    try:
        monkeypatch.setattr(state.heavenly_graph, 'has_idempotency_key', lambda **kwargs: True)
        with pytest.raises(ValueError, match='behavior_turn_receipt_invalid'):
            state.siming_runtime.plan_initial(SimingInput(input_type='esm_result_event', source_event=_authority_destruction_event()))
    finally:
        state.close()
