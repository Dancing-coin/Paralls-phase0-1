import pytest

from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime
from app.services.siming_quality_monitor import SimingQualityMonitor
from app.services.siming_state_tree import InMemorySimingStateTree
from test_siming_llm_runtime import make_visual_fact_event


class CapturingMonitor(SimingQualityMonitor):
    def evaluate(self, **kwargs):
        result = super().evaluate(**kwargs)
        self.snapshot = result.snapshot
        return result


def visual(kind='visual_object_fact', event_id='visual:1', **payload):
    event=make_visual_fact_event().model_copy(update={'event_id':event_id})
    event.payload.update(fact_type=kind, established_fact_id=event_id, target_object_id='letter',
                         visible_actor_ids=['char_a'], observability={'visual':True,'occluded':False})
    event.payload.update(payload)
    return event


def run(runtime, event):
    return runtime.tick([SimingInput(input_type='visual_fact_event',source_event=event)])


@pytest.mark.parametrize('kind', ['visual_character_fact','visual_object_fact','visual_environment_fact','visual_spatial_relation_fact'])
def test_siming_visual_protocol_consumes_primary_facts_and_records_visibility(kind):
    tree=InMemorySimingStateTree()
    monitor=CapturingMonitor()
    runtime=SimingRuntime(state_tree=tree, quality_monitor=monitor)
    result=run(runtime, visual(kind))
    summary=tree.latest_snapshot.environment.summary
    assert summary['visual_fact_sources']['visual:1']['category']==kind
    assert summary['visible_actor_ids']==['char_a']
    assert 'visual:1' in monitor.snapshot.known_fact_ids


def test_siming_visual_protocol_projection_requires_prior_same_scope_source():
    tree=InMemorySimingStateTree()
    monitor=CapturingMonitor()
    runtime=SimingRuntime(state_tree=tree, quality_monitor=monitor)
    run(runtime, visual())
    projection=visual('visual_evidence_projection','projection:1',source_visual_fact_event_id='visual:1')
    result=run(runtime,projection)
    assert tree.latest_snapshot.environment.summary['visual_evidence_refs']==['visual:1']
    assert tree.latest_snapshot.environment.summary['established_fact_id']=='visual:1'
    assert any('visual:1' in dim.evidence_refs for dim in monitor.snapshot.dimensions.values())


@pytest.mark.parametrize('mode',['missing','wrong_scope','future','wrong_object','raw','psychology','face_frame','null_observability','expired_source','unknown_type'])
def test_siming_visual_protocol_rejects_invalid_evidence_without_state_write(mode):
    tree=InMemorySimingStateTree()
    monitor=CapturingMonitor()
    runtime=SimingRuntime(state_tree=tree, quality_monitor=monitor)
    source=visual()
    run(runtime,source)
    prior=tree.latest_snapshot.model_dump()
    event=visual('visual_evidence_projection','projection:1',source_visual_fact_event_id='visual:1')
    if mode=='missing': event.payload['source_visual_fact_event_id']='absent'
    if mode=='wrong_scope': event=event.model_copy(update={'room_id':'another'})
    if mode=='future': event=event.model_copy(update={'producer_ts':299})
    if mode=='wrong_object': event.payload['target_object_id']='another'
    if mode=='raw': event.payload['skeleton_transforms']=[1,2,3]
    if mode=='unknown_type': event.payload['fact_type']='unregistered_visual_kind'
    if mode=='face_frame': event.payload['fact_type']='FacePoseFrame'
    if mode=='null_observability': event.payload['observability']=None
    if mode=='expired_source': event=event.model_copy(update={'producer_ts':source.producer_ts + source.ttl + 1})
    if mode=='psychology': event.payload['role_belief_truth']='guilty'
    result=run(runtime,event)
    assert tree.latest_snapshot.model_dump()==prior
    assert not any(item.output_type=='dispatch_intent' for item in result.outputs)
    assert any('visual_protocol_rejected' in item.reason for item in result.audit_records)


def test_siming_visual_protocol_projection_cannot_expand_visibility():
    tree=InMemorySimingStateTree()
    monitor=CapturingMonitor()
    runtime=SimingRuntime(state_tree=tree, quality_monitor=monitor)
    run(runtime,visual())
    run(runtime,visual('visual_evidence_projection','projection:1',
        source_visual_fact_event_id='visual:1',visible_actor_ids=['char_a','char_b']))
    assert tree.latest_snapshot.environment.summary['visible_actor_ids']==['char_a']


def test_siming_visual_protocol_visual_dispatch_keeps_source_and_requires_feedback():
    event=make_visual_fact_event()
    result=run(SimingRuntime(),event)
    output=next(item for item in result.outputs if item.output_type=='dispatch_intent')
    assert output.payload['source_visual_fact_event_id']==event.event_id
    assert output.payload['observability_goal']
    assert output.payload['presentation_budget']
    assert not any(audit.status=='effective' for audit in result.audit_records)


def test_siming_visual_protocol_planning_keeps_sources_uncommitted_until_install():
    tree = InMemorySimingStateTree()
    runtime = SimingRuntime(state_tree=tree)
    plan = runtime.plan_initial(SimingInput(input_type='visual_fact_event', source_event=visual()))
    assert tree.latest_snapshot is None
    assert 'visual:1' in plan.effects.state_tree.environment.summary['visual_fact_sources']
    runtime.install_planned_state(plan.effects)
    assert 'visual:1' in tree.latest_snapshot.environment.summary['visual_fact_sources']
    run(runtime, visual('visual_evidence_projection', 'projection:1', source_visual_fact_event_id='visual:1'))
    assert tree.latest_snapshot.environment.summary['visual_evidence_refs'] == ['visual:1']


def test_siming_visual_protocol_projection_normalizes_fact_without_rewriting_input():
    tree = InMemorySimingStateTree()
    runtime = SimingRuntime(state_tree=tree)
    run(runtime, visual())
    event = visual('visual_evidence_projection', 'projection:1', source_visual_fact_event_id='visual:1',
                   visible_actor_ids=['char_a', 'char_b'])
    received = []
    from types import SimpleNamespace
    def prepare(item, **kwargs):
        received.append(item.source_event)
        from app.services.siming_heavenly_runtime_support import PreparedHeavenlyDecision
        prepared = PreparedHeavenlyDecision(mode='off', event_family='visual_fact_event',
            owns_event_family=False, correlation_id=event.correlation_id, context_hash='test')
        return prepared, None, None
    runtime._heavenly_support = SimpleNamespace(prepare_request=prepare,
        plan_authority_outcome=lambda _: SimpleNamespace(batches=[]))
    plan = runtime.plan_initial(SimingInput(input_type='visual_fact_event', source_event=event))
    assert received[0].payload['established_fact_id'] == 'visual:1'
    assert received[0].payload['visible_actor_ids'] == ['char_a']
    assert plan.after.siming_input.source_event == event
    assert plan.after.observed[0].payload['established_fact_id'] == 'visual:1'
    assert event.payload['established_fact_id'] == 'projection:1'
