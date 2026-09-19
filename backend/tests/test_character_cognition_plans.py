"""认知结果先构造确定事件，再由原 session 阶段事务提交。"""
import json

import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from test_character_agent_cognition_writeback import _PositiveAffectStubL2


def test_cognition_update_plan_is_pure_json_and_matches_shared_sync_writeback(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    interpretation = _PositiveAffectStubL2().map_reasoning_output(actor_id='char_a', output={})
    before_state = runtime.get_dynamic_state_record('char_a').storage_dump()
    before_bundle = runtime.get_memory_record_bundle('char_a').model_dump(mode='json')
    writes = runtime._session_store._connection.total_changes
    events = runtime._plan_cognition_update(actor_id='char_a', producer_ts=42, interpretation=interpretation)
    assert json.loads(json.dumps(events)) == events
    assert runtime._session_store._connection.total_changes == writes
    assert runtime.get_session_timeline('char_a') == []
    assert runtime.get_dynamic_state_record('char_a').storage_dump() == before_state
    assert runtime.get_memory_record_bundle('char_a').model_dump(mode='json') == before_bundle
    assert [item['event_type'] for item in events] == [
        'knowledge_belief_event', 'social_cognition_event', 'higher_order_belief_event', 'dynamic_state_event']
    assert events[-1]['payload']['affect_state']['trust'] == .6
    runtime._apply_cognition_update(actor_id='char_a', producer_ts=42, interpretation=interpretation)
    actual = [{key: event[key] for key in ('event_type', 'producer_ts', 'payload')}
        for event in runtime.get_session_timeline('char_a')]
    assert actual == events
    expected_state = runtime.get_dynamic_state_record('char_a').storage_dump()
    runtime.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    assert restored.get_dynamic_state_record('char_a').storage_dump() == expected_state
    restored.close()


def test_goal_payload_plan_is_pure_and_preserves_transition_fields(tmp_path):
    from app.models.character_agent_runtime import CharacterIntentDecision

    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    decision = CharacterIntentDecision(actor_id='char_a', selected_intent='observe', persona_passed=True,
        logic_passed=True, gain_loss_passed=True, rationale='wait', primary_goal='watch', urgency='high')
    runtime._record_goal_state_event('char_a', 41, decision)
    changed = decision.model_copy(update={'primary_goal': 'protect', 'urgency': 'medium'})
    history = runtime.get_goal_state_history('char_a')
    writes = runtime._session_store._connection.total_changes
    payload = runtime._plan_goal_state_event('char_a', changed)
    assert runtime._session_store._connection.total_changes == writes
    assert runtime.get_goal_state_history('char_a') == history
    assert payload['goal_changed'] is True and 'primary_goal' in payload['changed_fields']
    assert json.loads(json.dumps(payload)) == payload
    runtime._record_goal_state_event('char_a', 42, changed)
    assert runtime.get_session_timeline('char_a')[-1]['payload'] == payload
    assert len(runtime.get_goal_state_history('char_a')) == len(history) + 1
    runtime.close()


@pytest.mark.parametrize('heavy', [False, True])
def test_runtime_reopen_finishes_only_exact_committed_stage_projection_suffix(tmp_path, monkeypatch, heavy):
    from app import main
    from app.config import Settings
    settings = Settings(heavenly_graph_path=str(tmp_path / 'graph.sqlite3'), siming_heavenly_mode='off')
    owner = main.build_runtime_state(settings) if heavy else CharacterAgentRuntime(storage_root=tmp_path)
    runtime = owner.character_agent_runtime if heavy else owner
    interpretation = _PositiveAffectStubL2().map_reasoning_output(actor_id='char_a', output={})
    events = runtime._plan_cognition_update(actor_id='char_a', producer_ts=42, interpretation=interpretation)
    receipt = runtime._session_store.commit_cognition_stage(actor_id='char_a', key='dispatch:1/char_a/l2/0',
        expected_revision=0, events=events, before={'stage': 'l2'}, after={'stage': 'l3'})
    # 首个 graph 投影已成功，其余提交事件尚未投影即退出。
    runtime._project_session_event(receipt['events'][0])
    owner.close()
    from app.character_agent.storage.session_store import CharacterAgentSessionStore
    with monkeypatch.context() as scope:
        scope.setattr(CharacterAgentSessionStore, 'list_events', lambda *a: pytest.fail('full history scan'))
        owner = main.build_runtime_state(settings) if heavy else CharacterAgentRuntime(storage_root=tmp_path)
        restored = owner.character_agent_runtime if heavy else owner
    restored._memory_store.bind_session_reader(restored._session_store.list_events)
    store = restored._session_store
    assert store.event_count('char_a') == 4
    assert store.projection_cursor('char_a', 'memory') == 4
    assert store.projection_cursor('char_a', 'ask') == 4
    assert restored.get_dynamic_state_record('char_a').affect_state.trust == .6
    bundle = restored.get_memory_record_bundle('char_a')
    assert len(bundle.knowledge_memories) == len(bundle.social_memories) == len(bundle.higher_order_memories) == 1
    assert store.commit_cognition_stage(**receipt['plan']) == receipt
    assert restored.get_session_timeline('char_a') == receipt['events']
    owner.close()


@pytest.mark.parametrize('corruption', ['missing_pointer', 'wrong_digest', 'missing_receipt', 'changed_event'])
def test_cognition_stage_projection_requires_exact_receipt_and_original_events(tmp_path, corruption):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    store = runtime._session_store
    interpretation = _PositiveAffectStubL2().map_reasoning_output(actor_id='char_a', output={})
    receipt = store.commit_cognition_stage(actor_id='char_a', key='dispatch:1/char_a/l2/0',
        expected_revision=0, events=runtime._plan_cognition_update(actor_id='char_a', producer_ts=42,
            interpretation=interpretation), before={'stage': 'l2'}, after={'stage': 'l3'})
    with store.transaction():
        state = store.read_runtime_state('char_a')
        if corruption == 'missing_pointer':
            state.pop('cognition_stage')
            store._write_runtime_state('char_a', state)
        elif corruption == 'wrong_digest':
            state['cognition_stage']['input_digest'] = 'wrong'
            store._write_runtime_state('char_a', state)
        elif corruption == 'missing_receipt':
            store._connection.execute("DELETE FROM character_session_receipts WHERE kind='cognition_stage'")
        else:
            event = receipt['events'][-1]
            event['payload']['affect_state']['trust'] = .1
            store._connection.execute('UPDATE character_session_events SET payload_json=? WHERE event_id=?',
                (json.dumps(event), event['event_id']))
    with pytest.raises(ValueError, match='projection_rebuild_required|projection_proof_invalid|event_missing_or_conflicting'):
        runtime._finish_session_projections('char_a')
    assert store.projection_cursor('char_a', 'memory') == 0
    assert store.projection_cursor('char_a', 'ask') == 0
    runtime.close()
