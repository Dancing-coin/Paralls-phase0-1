from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime
from app.services.siming_continuation import SimingStageEffects
from test_siming_fact_locking import event


def item(**kwargs):
    observed = event(**kwargs)
    source = observed.authority_event.model_copy(update={'payload': observed.payload})
    return SimingInput(input_type='world_fact_event', source_event=source)


def test_siming_runtime_fact_veto_is_audited_before_narrative_update():
    runtime = SimingRuntime()
    runtime.tick([item()])
    runtime.tick([item(operation='advance_phase', ts=11, fact_phase='T1')])
    runtime.tick([item(operation='advance_phase', ts=12, fact_phase='T2')])
    before = dict(runtime._narrative_core._revision_by_room)
    result = runtime.tick([item(fact_id='new', ts=13)])
    assert any(a.reason == 'fact_veto:fact_set_locked' for a in result.audit_records)
    assert runtime._narrative_core._revision_by_room == before
    assert not any(output.output_type == 'dispatch_intent' for output in result.outputs)


def test_siming_fact_planning_is_pure_and_json_effects_restore_locks():
    runtime = SimingRuntime()
    first = item()
    plan = runtime.plan_initial(first)
    assert runtime._fact_core.snapshot_for(first.source_event) is None
    assert plan.effects.fact_core_states[0].facts
    runtime.install_planned_state(plan.effects)
    for index in (1, 2):
        plan = runtime.plan_initial(item(operation='advance_phase', ts=10+index, fact_phase=f'T{index}'))
        runtime.install_planned_state(plan.effects)
    effects = SimingStageEffects.model_validate_json(plan.effects.model_dump_json())
    restored = SimingRuntime()
    restored.install_planned_state(effects)
    assert restored.tick([item(fact_id='new', ts=20)]).audit_records[0].reason == 'fact_veto:fact_set_locked'
    assert plan.after.siming_input.source_event.payload['fact_phase'] == 'T2'


def test_siming_fact_snapshot_survives_unrelated_plan_and_rejected_input():
    runtime = SimingRuntime()
    runtime.install_planned_state(runtime.plan_initial(item()).effects)
    rejected = runtime.plan_initial(item(fact_id='fact:culprit', value='other', ts=11))
    assert rejected.effects.fact_core_states[0].facts['fact:culprit'].value == 'char_a'
    restored = SimingRuntime()
    restored.install_planned_state(SimingStageEffects.model_validate_json(rejected.effects.model_dump_json()))
    assert restored._fact_core.snapshot_for(item().source_event).facts

def test_siming_fact_state_survives_provider_continuation():
    from app.services.siming_continuation import run_siming_provider, SimingProviderCompletion
    from test_siming_llm_runtime import make_visual_fact_event
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    runtime.tick([item()])
    pending = runtime.prepare_tick(SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event()))
    completion = SimingProviderCompletion.model_validate_json(
        run_siming_provider(runtime._llm_provider, pending.job.request_json))
    plan = runtime.plan_accepted(runtime.export_turn(pending.job.turn_id), completion)
    assert plan.effects.fact_core_states[0].facts['fact:culprit'].value == 'char_a'
    restored = SimingRuntime()
    restored.install_planned_state(SimingStageEffects.model_validate_json(plan.effects.model_dump_json()))
    assert restored._fact_core.snapshot_for(item().source_event).facts


def test_siming_coordinator_fact_state_survives_database_reopen(tmp_path):
    from app import main
    from app.config import Settings
    from test_siming_coordinator import coordinator
    settings = Settings(siming_heavenly_mode='active', heavenly_graph_path=str(tmp_path / 'facts.db'))
    state = main.build_runtime_state(settings)
    try:
        owner = coordinator(state)
        from app.services.siming_event_pipeline import SimingEventPipeline
        from app.services.siming_event_consumer import SimingEventConsumer
        from app.services.siming_event_producer import SimingEventProducer
        from app.services.siming_audit_writer import SimingAuditWriter
        from app.services.authority_event_bus import InMemoryAuthorityEventBus
        bus = InMemoryAuthorityEventBus()
        owner.output_pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(),
            runtime=state.siming_runtime, producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter())
        for message in [item(), item(operation='advance_phase', ts=11, fact_phase='T1'),
                        item(operation='advance_phase', ts=12, fact_phase='T2')]:
            receipt = owner.admit_event(message.source_event, now=100, expires_at=200, policy_version='policy:v1')
            owner.begin(receipt.entry.key, now=101)
            owner.resume_committed(receipt.entry.key, now=102)
            assert owner._provider_plan_pin_is_current(owner.admissions.read(receipt.entry.key).entry,
                                                        owner.read_plan(receipt.entry.key))
    finally:
        state.close()
    restored = main.build_runtime_state(settings)
    try:
        owner = coordinator(restored)
        receipt = owner.admit_event(item(fact_id='new', ts=20).source_event,
                                    now=103, expires_at=200, policy_version='policy:v1')
        owner.begin(receipt.entry.key, now=104)
        plan = owner.read_plan(receipt.entry.key)
        assert any(a.reason == 'fact_veto:fact_set_locked' for a in plan.after.result.audit_records)
        assert plan.effects.fact_core_states[0].phase == 'T2'
    finally:
        restored.close()

def test_siming_room_effects_preserve_other_scene_lock():
    runtime = SimingRuntime()
    for message in [item(), item(operation='advance_phase', ts=11, fact_phase='T1'),
                    item(operation='advance_phase', ts=12, fact_phase='T2')]:
        runtime.install_planned_state(runtime.plan_initial(message).effects)
    other = item(fact_id='other', ts=20)
    other.source_event.scene_id = 'scene_other'
    plan = runtime.plan_initial(other)
    restored = SimingRuntime()
    restored.install_planned_state(SimingStageEffects.model_validate_json(plan.effects.model_dump_json()))
    result = restored.tick([item(fact_id='new', ts=30)])
    assert any(a.reason == 'fact_veto:fact_set_locked' for a in result.audit_records)
