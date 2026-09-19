import pytest
from app import main
from app.config import Settings
from test_siming_heavenly_runtime_composition import _prepare_staged_graph_dispatch


@pytest.mark.parametrize('accepted', [True, False])
def test_staging_ack_plan_matches_original_batches_without_writes(tmp_path, accepted):
    states = [main.build_runtime_state(Settings(siming_heavenly_mode='active', heavenly_graph_path=str(tmp_path / f'{i}.db'))) for i in range(2)]
    try:
        events = [_prepare_staged_graph_dispatch(state) for state in states]
        if not accepted:
            events = [event.model_copy(update={'source_event': event.source_event.model_copy(update={'payload': {**event.source_event.payload, 'accepted': False, 'reason': 'esm_rejected'}})}) for event in events]
        graph = states[0].heavenly_graph
        before = graph._connection.total_changes
        plan = states[0].siming_runtime.plan_initial(events[0])
        assert graph._connection.total_changes == before
        batches = []
        original = states[1].heavenly_graph.write_batch
        def capture(batch):
            batches.append(batch)
            return original(batch)
        states[1].heavenly_graph.write_batch = capture
        expected = states[1].siming_runtime.tick([events[1]])
        assert plan.after.result == expected
        assert plan.effects.batches == batches
        for batch in plan.effects.batches:
            graph.write_batch(batch)
        for batch in plan.effects.batches:
            assert graph.write_batch(batch).replayed
    finally:
        for state in states:
            state.close()

def test_nested_publication_admission_preserves_room_tail(tmp_path):
    import time
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_event_pipeline import SimingEventPipeline
    from app.services.siming_event_consumer import SimingEventConsumer
    from app.services.siming_event_producer import SimingEventProducer
    from app.services.siming_audit_writer import SimingAuditWriter
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    from app.services.siming_continuation import run_siming_provider
    from test_siming_continuation import make_visual_fact_event
    from test_siming_coordinator import coordinator
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / 'nested.db')))
    try:
        state.siming_runtime = SimingRuntime()
        owner = coordinator(state)
        bus = InMemoryAuthorityEventBus()
        owner.output_pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(), runtime=state.siming_runtime,
            producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter())
        event = make_visual_fact_event()
        now = time.time()
        key = owner.admit_event(event, now=now, expires_at=now+60, policy_version='v1').entry.key
        children = []
        def nested(_):
            children.append(owner.admit_event(event.model_copy(update={'event_id': 'nested'}),
                now=now, expires_at=now+60, policy_version='v1').entry)
        bus.subscribe('*', nested)
        owner.begin(key, now=now)
        owner.resume_committed(key, now=now)
        job = owner.prepare_provider(key, now=now).job
        owner.accept_provider(key, job, run_siming_provider(state.siming_runtime._llm_provider, job.request_json), now=now)
        owner.freeze_result(key, now=now)
        assert owner.resume_committed(key, now=now).entry.state == 'completed'
        head = owner.admissions.read_room_head(key.scope)
        assert children and head.last_sequence == 2 and head.completed_sequence == 1
        assert owner.take_ready(now=now) == (children[0].key,)
    finally:
        state.close()
