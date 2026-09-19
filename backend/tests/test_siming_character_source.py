import time
import pytest
from app import main
from app.config import Settings
from app.models.authority_event import AuthorityEvent
from app.services.siming_runtime import SimingRuntime
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_continuation import run_siming_provider
from test_siming_continuation import ThreadProvider, make_candidate, make_visual_fact_event
from test_siming_coordinator import coordinator


def test_character_delivery_requires_original_committed_and_published_parent(tmp_path):
    settings = Settings(heavenly_graph_path=str(tmp_path / 'parent.db'))
    state = main.build_runtime_state(settings)
    try:
        state.siming_runtime = SimingRuntime(llm_provider=ThreadProvider([make_candidate(target_environment_id=None)]))
        owner = coordinator(state)
        bus = InMemoryAuthorityEventBus()
        owner.output_pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(), runtime=state.siming_runtime,
            producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter(),
            character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=state.character_agent_runtime))
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now+60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        owner.resume_committed(key, now=now)
        job = owner.prepare_provider(key, now=now).job
        owner.accept_provider(key, job, run_siming_provider(state.siming_runtime._llm_provider, job.request_json), now=now)
        committed = owner.freeze_result(key, now=now).entry
        delivery = next(effect for effect in committed.transition.effects if effect.kind == 'character_delivery')
        event = AuthorityEvent.model_validate(delivery.payload['event'])
        payload = delivery.payload['delivery']
        with pytest.raises(ValueError, match='siming_character_source_unconfirmed'):
            owner.character_delivery_proof(event, payload)
        owner.resume_committed(key, now=now)
        before = state.heavenly_graph._connection.total_changes
        proof = owner.character_delivery_proof(event, payload)
        assert proof['effect_key'] == delivery.effect_key
        assert proof['commit_revision'] == committed.commit_revision
        assert proof['expires_at'] == committed.expires_at
        assert state.heavenly_graph._connection.total_changes == before
        for forged in [event.model_copy(update={'causation_id': 'missing'}),
                       event.model_copy(update={'payload': {**event.payload, 'pressure_hint': 'forged'}})]:
            with pytest.raises(ValueError, match='siming_character_source'):
                owner.character_delivery_proof(forged, payload)
        with pytest.raises(ValueError, match='siming_character_source'):
            owner.character_delivery_proof(event, {**payload, 'delivery_id': 'forged'})
        state.close()
        state = main.build_runtime_state(settings)
        restored = coordinator(state)
        before = state.heavenly_graph._connection.total_changes
        assert restored.character_delivery_proof(event, payload) == proof
        assert state.heavenly_graph._connection.total_changes == before
    finally:
        state.close()
