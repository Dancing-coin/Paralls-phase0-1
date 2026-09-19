"""真实 Siming 初始领域提交的只读证明，不用网络/HTTP ACK 代替原账本。"""
import json

import pytest

from scripts.verification import population_mixed_siming as proof


def test_original_siming_revisions_and_graph_effects_are_replayed_without_writes(tmp_path):
    from app import main
    from app.config import Settings
    from test_siming_coordinator import coordinator
    from test_siming_heavenly_runtime_composition import _authority_destruction_event
    database = tmp_path / 'graph.db'
    state = main.build_runtime_state(Settings(siming_heavenly_mode='active', heavenly_graph_path=str(database),
        character_model_provider_kind='local', siming_llm_mode='disabled'))
    try:
        owner = coordinator(state)
        entry = owner.admit_event(_authority_destruction_event(), now=100., expires_at=200., policy_version='v1').entry
        owner.begin(entry.key, now=101.)
        done = owner.resume_committed(entry.key, now=102.).entry
        assert done.state == 'commit_started'
        changes = state.heavenly_graph._connection.total_changes
        path = tmp_path / 'siming.jsonl'
        proof.export_siming(database, path)
        result = proof.verify_siming(path, character_jobs=[])
        assert result['states'] == {'commit_started': 1} and result['completed'] == 0
        assert result['graph_effects'] >= 14
        assert state.heavenly_graph._connection.total_changes == changes
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        changed = tmp_path / 'changed.jsonl'
        for failure in ('revision_gap', 'receipt_missing', 'effect_changed', 'pending_lost'):
            values = json.loads(json.dumps(rows))
            if failure == 'revision_gap':
                values = [row for row in values if row['type'] != 'siming_revision' or row['node']['revision'] != 2]
            elif failure == 'receipt_missing':
                values = [row for row in values if row['type'] != 'siming_graph_effect']
            elif failure == 'effect_changed':
                row = next(row for row in values if row['type'] == 'siming_graph_effect')
                row['nodes'][0]['attributes']['forged'] = True
            else:
                next(row for row in values if row['type'] == 'siming_job_end')['pending'] = None
            changed.write_text('\n'.join(json.dumps(row) for row in values)+'\n', encoding='utf-8')
            with pytest.raises(ValueError):
                proof.verify_siming(changed, character_jobs=[])
    finally:
        state.close()


def test_completed_parent_requires_original_child_admission_and_provider_result(tmp_path):
    import time
    from app import main
    from app.config import Settings
    from app.services.siming_runtime import SimingRuntime
    from app.services.siming_continuation import run_siming_provider
    from app.services.siming_event_pipeline import SimingEventPipeline
    from app.services.siming_event_consumer import SimingEventConsumer
    from app.services.siming_event_producer import SimingEventProducer
    from app.services.siming_audit_writer import SimingAuditWriter
    from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    from app.character_agent.services.cognition_admission import CharacterCognitionAdmissionService
    from app.character_agent.storage.session_store import CharacterAgentSessionStore
    from scripts.verification.population_mixed_cognition import export_character, verify_character
    from test_siming_coordinator import coordinator
    from test_siming_continuation import ThreadProvider, make_candidate, make_visual_fact_event
    database = tmp_path / 'graph.db'
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(database), character_model_provider_kind='local', siming_llm_mode='disabled'))
    session = CharacterAgentSessionStore(database_path=tmp_path / 'children.db')
    session.initialize_recovery()
    try:
        state.siming_runtime = SimingRuntime(llm_provider=ThreadProvider([make_candidate(target_environment_id=None)]))
        bus = InMemoryAuthorityEventBus()
        owner = coordinator(state)
        owner.output_pipeline = SimingEventPipeline(bus=bus, consumer=SimingEventConsumer(), runtime=state.siming_runtime,
            producer=SimingEventProducer(bus), audit_writer=SimingAuditWriter(),
            character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=state.character_agent_runtime))
        owner.character_admissions = CharacterCognitionAdmissionService(store=session, assert_owner=lambda: None,
            validate_source=lambda _: None, activation_is_current=lambda *_: False, delivery_pin_reader=lambda *_: {'source': 1, 'actor': 1})
        now = time.time()
        key = owner.admit_event(make_visual_fact_event(), now=now, expires_at=now+60, policy_version='v1').entry.key
        owner.begin(key, now=now)
        owner.resume_committed(key, now=now)
        job = owner.prepare_provider(key, now=now).job
        owner.accept_provider(key, job, run_siming_provider(state.siming_runtime._llm_provider, job.request_json), now=now)
        owner.freeze_result(key, now=now)
        assert owner.resume_committed(key, now=now).entry.state == 'completed'
        export_character(tmp_path / 'children.db', tmp_path / 'children.jsonl')
        children = verify_character(tmp_path / 'children.jsonl')
        assert children['completed'] == 0 and children['pending'] > 0
        path = tmp_path / 'siming.jsonl'
        proof.export_siming(database, path)
        result = proof.verify_siming(path, character_jobs=children['jobs'])
        assert result['completed'] == 1 and result['pending'] == 0
        provider = result['jobs'][0]['providers'][0]
        assert provider['stage'] == 'candidate' and provider['error'] == '' and provider['output_sha256']
        with pytest.raises(ValueError, match='original_admission_missing'):
            proof.verify_siming(path, character_jobs=[])
    finally:
        session.close()
        state.close()
