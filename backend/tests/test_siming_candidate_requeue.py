"""同一原来源 candidate 的 timeline 失效重排；不重放初始事实。"""
import time
import pytest
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
from test_siming_coordinator import coordinator
from test_siming_continuation import ThreadProvider, make_candidate, make_visual_fact_event


def open_owner(tmp_path, versions):
    state=main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path/'graph.db'), character_model_provider_kind='local',siming_llm_mode='disabled'))
    state.siming_runtime=SimingRuntime(llm_provider=ThreadProvider([make_candidate(target_environment_id=None)]))
    owner=coordinator(state)
    owner.runtime._actor_pin_reader=lambda actor: (('control', 'auto'), ('timeline', versions[0]))
    bus=InMemoryAuthorityEventBus()
    owner.output_pipeline=SimingEventPipeline(bus=bus,consumer=SimingEventConsumer(),runtime=owner.runtime,
        producer=SimingEventProducer(bus),audit_writer=SimingAuditWriter(),
        character_dispatch_adapter=SimingCharacterDispatchAdapter(runtime=state.character_agent_runtime))
    session=CharacterAgentSessionStore(database_path=tmp_path/'children.db')
    session.initialize_recovery()
    owner.character_admissions=CharacterCognitionAdmissionService(store=session,assert_owner=lambda:None,
        validate_source=lambda _:None,activation_is_current=lambda *_:False,delivery_pin_reader=lambda *_:{'source':1,'actor':1})
    return state,session,owner


def pending(owner):
    now=time.time()
    key=owner.admit_event(make_visual_fact_event(),now=now,expires_at=now+30,policy_version='v1').entry.key
    owner.begin(key,now=now)
    owner.resume_committed(key,now=now)
    advance=owner.prepare_provider(key,now=now)
    entry=owner.admissions.read(key).entry
    completion=run_siming_provider(owner.runtime._llm_provider,advance.job.request_json)
    return key,advance.job,entry,completion


@pytest.mark.parametrize('restart',[False,True])
def test_candidate_stale_completion_requeues_original_identity_without_replaying_prefix(tmp_path,monkeypatch,restart):
    versions=[1]
    state,session,owner=open_owner(tmp_path,versions)
    try:
        key,job,original,completion=pending(owner)
        head=owner.admissions.read_room_head(key.scope)
        versions[0]=2
        rejected=owner.accept_provider(key,job,completion,now=time.time(),provider_revision=original.provider_revision)
        assert rejected.entry.state=='requeued'
        assert rejected.entry.expires_at==original.expires_at
        assert owner.admissions.read_room_head(key.scope)==head
        assert owner.accept_provider(key,job,completion,now=time.time(),provider_revision=original.provider_revision).replayed
        if restart:
            session.close();state.close()
            state,session,owner=open_owner(tmp_path,versions)
        monkeypatch.setattr(owner.runtime,'plan_initial',lambda *_:pytest.fail('original prefix replayed'))
        prepared=owner.prepare_ready(key,now=time.time())
        next_job,provider,next_revision=prepared
        assert next_job.token!=job.token and next_job.attempt==job.attempt+1
        assert next_job.request_json==job.request_json
        assert next_revision>original.provider_revision
        changes=state.heavenly_graph._connection.total_changes
        assert owner.accept_provider(key,job,completion,now=time.time(),provider_revision=original.provider_revision).replayed
        assert state.heavenly_graph._connection.total_changes==changes
        done=owner.finish_ready(key,next_job,run_siming_provider(provider,next_job.request_json),provider_revision=next_revision,now=time.time())
        assert done.entry.state=='completed'
        assert done.entry.expires_at==original.expires_at
        assert owner.admissions.read(key,revision=original.provider_revision+1).entry.state=='requeued'
        assert owner.admissions.read_room_head(key.scope).completed_sequence==original.room_sequence
    finally:
        session.close();state.close()


@pytest.mark.parametrize('cut', ['before_requeue', 'after_requeue', 'before_result'])
def test_requeue_write_cuts_restore_without_initial_replay(tmp_path, monkeypatch, cut):
    versions = [1]
    state, session, owner = open_owner(tmp_path, versions)
    try:
        key, job, original, completion = pending(owner)
        versions[0] = 2
        advance = owner.admissions.advance
        def fail_write(*args, **kwargs):
            if cut == 'after_requeue':
                advance(*args, **kwargs)
            raise OSError('injected ledger cut')
        if cut != 'before_result':
            monkeypatch.setattr(owner.admissions, 'advance', fail_write)
            with pytest.raises(OSError):
                owner.accept_provider(key, job, completion, now=time.time())
        session.close(); state.close()
        state, session, owner = open_owner(tmp_path, versions)
        monkeypatch.setattr(owner.runtime, 'plan_initial', lambda *_: pytest.fail('prefix replay'))
        if cut != 'after_requeue':
            assert owner.prepare_ready(key, now=time.time()) is None
            assert owner.admissions.read(key).entry.state == 'requeued'
        next_job, provider, revision = owner.prepare_ready(key, now=time.time())
        done = owner.finish_ready(key, next_job, run_siming_provider(provider, next_job.request_json),
            provider_revision=revision, now=time.time())
        assert done.entry.state == 'completed' and done.entry.expires_at == original.expires_at
    finally:
        session.close(); state.close()


@pytest.mark.parametrize('change', ['control', 'source', 'expired', 'requeued_expired', 'requeued_source'])
def test_requeue_never_renews_budget_or_ignores_other_dependencies(tmp_path, change):
    versions = [1]
    state, session, owner = open_owner(tmp_path, versions)
    try:
        key, job, original, completion = pending(owner)
        versions[0] = 2
        now = time.time()
        if change.startswith('requeued_'):
            owner.accept_provider(key, job, completion, now=now)
        if change == 'control':
            owner.runtime._actor_pin_reader = lambda actor: (('control', 'off'), ('timeline', 2))
        if change.endswith('source'):
            owner._invalidation_reader = lambda _: 'source_revoked'
        if change.endswith('expired'):
            now = original.expires_at + 1
        if change.startswith('requeued_'):
            assert owner.prepare_ready(key, now=now) is None
            result = owner.admissions.read(key)
        else:
            result = owner.accept_provider(key, job, completion, now=now)
        assert result.entry.state == 'stale'
        assert result.entry.expires_at == original.expires_at
    finally:
        session.close(); state.close()


def test_requeue_original_receipts_and_unique_attempts_survive_offline_proof(tmp_path):
    import json
    from scripts.verification.population_mixed_siming import export_siming, verify_siming
    from scripts.verification.population_mixed_cognition import export_character, verify_character
    versions = [1]
    state, session, owner = open_owner(tmp_path, versions)
    try:
        key, job, original, completion = pending(owner)
        versions[0] = 2
        owner.accept_provider(key, job, completion, now=time.time())
        new_job, provider, revision = owner.prepare_ready(key, now=time.time())
        owner.finish_ready(key, new_job, run_siming_provider(provider, new_job.request_json), provider_revision=revision, now=time.time())
        export_character(tmp_path/'children.db', tmp_path/'children.jsonl')
        children = verify_character(tmp_path/'children.jsonl')['jobs']
        export_siming(tmp_path/'graph.db', tmp_path/'siming.jsonl')
        result = verify_siming(tmp_path/'siming.jsonl', character_jobs=children)
        assert result['states'] == {'completed': 1}
        bindings = result['jobs'][0]['providers']
        assert len(bindings) == 2 and bindings[0]['rejected_revision'] == original.provider_revision + 1
        from scripts.verification.population_mixed_verification import verify_siming_provider_calls
        calls = [dict(family='siming', request_sha256=binding['request_sha256'], output_sha256=binding['output_sha256']) for binding in bindings]
        verify_siming_provider_calls(result['jobs'], calls)
        with pytest.raises(ValueError, match='original_provider_result_missing'):
            verify_siming_provider_calls(result['jobs'], calls[:1])
        rows = [json.loads(line) for line in (tmp_path/'siming.jsonl').read_text(encoding='utf-8').splitlines()]
        for row in rows:
            if row['type'] == 'siming_revision' and row['node']['revision'] == original.provider_revision + 1:
                row['node']['attributes']['transition']['reason'] = 'forged'
        (tmp_path/'bad.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows), encoding='utf-8')
        with pytest.raises(ValueError):
            verify_siming(tmp_path/'bad.jsonl', character_jobs=children)
    finally:
        session.close(); state.close()


def test_requeue_holds_room_order_and_cannot_rewrite_rejected_result(tmp_path):
    from app.services.siming_continuation import SimingProviderCompletion
    versions = [1]
    state, session, owner = open_owner(tmp_path, versions)
    try:
        key, job, original, completion = pending(owner)
        source = make_visual_fact_event().model_copy(update={'event_id': 'later-room-source'})
        later = owner.admit_event(source, now=time.time(), expires_at=original.expires_at, policy_version='v1').entry
        versions[0] = 2
        owner.accept_provider(key, job, completion, now=time.time())
        assert owner.take_ready(now=time.time()) == (key,)
        changed = SimingProviderCompletion.model_validate_json(completion).model_copy(update={'candidates': []}).model_dump_json().encode()
        changes = state.heavenly_graph._connection.total_changes
        with pytest.raises(ValueError, match='completion_conflict'):
            owner.accept_provider(key, job, changed, now=time.time())
        assert state.heavenly_graph._connection.total_changes == changes
        next_job, provider, revision = owner.prepare_ready(key, now=time.time())
        owner.finish_ready(key, next_job, run_siming_provider(provider, next_job.request_json), provider_revision=revision, now=time.time())
        assert owner.take_ready(now=time.time()) == (later.key,)
    finally:
        session.close(); state.close()


@pytest.mark.parametrize('restart', [False, True])
def test_real_character_tuple_pin_requeues_after_original_session_append(tmp_path, restart):
    state, session, owner = open_owner(tmp_path, [1])
    try:
        runtime = state.character_agent_runtime
        owner.runtime._actor_pin_reader = lambda actor: runtime._capture_cognition_pin(actor) if runtime.supports_actor(actor) else {'supported': False}
        key, job, original, completion = pending(owner)
        before = dict(runtime._capture_cognition_pin('char_b'))
        runtime._append_session_event('char_b', 'external_observation', 301, {'summary': 'later fact'})
        after = dict(runtime._capture_cognition_pin('char_b'))
        assert [name for name in before if before[name] != after[name]] == ['timeline']
        if restart:
            session.close(); state.close()
            state, session, owner = open_owner(tmp_path, [1])
            runtime = state.character_agent_runtime
            owner.runtime._actor_pin_reader = lambda actor: runtime._capture_cognition_pin(actor) if runtime.supports_actor(actor) else {'supported': False}
            assert owner.prepare_ready(key, now=time.time()) is None
            assert owner.admissions.read(key).entry.state == 'requeued'
        else:
            assert owner.accept_provider(key, job, completion, now=time.time()).entry.state == 'requeued'
        next_job, provider, revision = owner.prepare_ready(key, now=time.time())
        assert next_job.attempt == job.attempt + 1
        result = owner.finish_ready(key, next_job, run_siming_provider(provider, next_job.request_json),
            provider_revision=revision, now=time.time())
        assert result.entry.state == 'completed' and result.entry.expires_at == original.expires_at
    finally:
        session.close(); state.close()


@pytest.mark.parametrize('replacement', [
    [['timeline', 'new'], ['timeline', 'old']],
    [['control', 'same']],
    [['timeline', 'new'], ['control', 'changed']],
    [['timeline', 'new'], ['control', 'same'], ['extra', 'value']],
    [['timeline', 'new'], ['control']],
])
def test_tuple_pin_requeue_rejects_malformed_or_other_changes(replacement):
    from app.services.siming_continuation import candidate_timeline_changed
    original = {'actors': {'char_b': [['control', 'same'], ['timeline', 'old']]}}
    assert not candidate_timeline_changed(original, {'actors': {'char_b': replacement}})
