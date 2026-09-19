import pytest
from app.models.siming_heavenly_graph import HeavenlyGraphScope, HeavenlyNodeQuery
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from test_siming_llm_runtime import make_visual_fact_event


def scope():
    return HeavenlyGraphScope(world_id='world', session_id='session', story_branch_id='main')


def service(graph):
    from app.services.siming_admission import SimingAdmissionService
    from app.services.siming_heavenly_memory import SimingHeavenlyMemoryService
    return SimingAdmissionService(SimingHeavenlyMemoryService(graph))


@pytest.mark.parametrize('sqlite', [False, True])
def test_admission_durable_identity_full_source_conflict_and_context_isolation(tmp_path, sqlite):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db') if sqlite else InMemoryHeavenlyGraphAdapter()
    api = service(graph)
    event = make_visual_fact_event()
    first = api.admit(scope=scope(), source=event, now=100, expires_at=200, policy_version='policy:v1')
    second = api.admit(scope=scope(), source=event, now=101, expires_at=201, policy_version='policy:v1')
    assert second.replayed and second.entry == first.entry
    assert first.entry.source == event.model_dump(mode='json')
    changed = event.model_copy(deep=True)
    changed.payload['changed'] = True
    with pytest.raises(ValueError, match='source_conflict'):
        api.admit(scope=scope(), source=changed, now=102, expires_at=202, policy_version='policy:v1')
    assert graph.query_nodes(HeavenlyNodeQuery(scope=scope(), valid_at=1000)) == []
    assert api.read(first.entry.key).entry == first.entry
    if sqlite:
        graph.close()
        reopened = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
        assert service(reopened).read(first.entry.key).entry == first.entry
        reopened.close()


def test_pending_more_than_thousand_bounded_pages_and_terminal_exact_read(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    keys = []
    for index in range(1007):
        event = make_visual_fact_event().model_copy(update={'event_id': f'event:{index}'})
        keys.append(api.admit(scope=scope(), source=event, now=100, expires_at=200, policy_version='v1').entry.key)
    terminal = api.advance(keys[50], expected_revision=1,
        transition=SimingAdmissionTransition(state='cancelled', reason='revoked'), now=101)
    seen, cursor = [], None
    while True:
        page = api.list_pending(scope=scope(), limit=31, cursor=cursor)
        assert len(page.entries) <= 31
        seen.extend(item.key.entry_id for item in page.entries)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 1006
    assert keys[50].entry_id not in seen
    assert api.read(keys[50]).entry == terminal.entry
    graph.close()

def prepared_provider():
    from app.models.siming_event import SimingInput
    from app.models.siming_heavenly_memory import SimingAdmissionProvider
    from app.services.siming_runtime import SimingRuntime
    runtime = SimingRuntime(actor_pin_reader=lambda _: 1, source_pin_reader=lambda _: True)
    pending = runtime.prepare_tick(SimingInput(input_type='visual_fact_event', source_event=make_visual_fact_event()))
    return SimingAdmissionProvider(provider_identity='candidate:stub', request_json=pending.job.request_json.decode(),
        frame_json=runtime.export_turn(pending.job.turn_id).decode(), pin_digest=pending.job.pin_digest)


def test_state_machine_provider_and_completion_validation_and_historical_replay(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition, SimingAdmissionEffect, SimingAdmissionEffectReceipt
    from app.services.siming_continuation import SimingProviderCompletion
    import hashlib
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    entry = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    key = entry.key
    with pytest.raises(ValueError, match='transition'):
        api.advance(key, expected_revision=1, transition=SimingAdmissionTransition(state='completed'), now=101)
    provider = prepared_provider()
    freeze = SimingAdmissionTransition(state='provider_pending', stage='candidate', provider=provider)
    frozen = api.advance(key, expected_revision=1, transition=freeze, now=101)
    bad = SimingAdmissionTransition(state='result_ready', stage='candidate', completion_json='{"request_digest":"wrong"}')
    with pytest.raises(ValueError, match='request_digest'):
        api.advance(key, expected_revision=2, transition=bad, now=102)
    completion = SimingProviderCompletion(request_digest=hashlib.sha256(provider.request_json.encode()).hexdigest()).model_dump_json()
    ready = SimingAdmissionTransition(state='result_ready', stage='candidate', completion_json=completion)
    api.advance(key, expected_revision=2, transition=ready, now=102)
    effect = SimingAdmissionEffect(effect_key=key.effect_key('candidate', 0, 0), kind='dispatch', payload={'target':'char_b'})
    plan = SimingAdmissionTransition(state='commit_started', stage='candidate', effects=[effect])
    api.advance(key, expected_revision=3, transition=plan, now=103)
    with pytest.raises(ValueError, match='receipt'):
        api.advance(key, expected_revision=4, transition=SimingAdmissionTransition(state='completed'), now=104)
    receipt = SimingAdmissionEffectReceipt(effect_key=effect.effect_key, receipt={'dispatch_event_id':'dispatch:1'})
    done = api.advance(key, expected_revision=4, transition=SimingAdmissionTransition(state='completed', receipts=[receipt]), now=104)
    replay = api.advance(key, expected_revision=1, transition=freeze, now=999)
    assert replay.replayed and replay.entry == frozen.entry
    assert api.list_pending(scope=scope()).entries == []
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    assert service(graph).read(key).entry == done.entry
    assert service(graph).read(key, revision=2).entry.transition.provider == provider
    graph.close()


def test_provider_frame_binding_expiry_and_explicit_requeue(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    entry = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    provider = prepared_provider()
    with pytest.raises(ValueError, match='pin'):
        api.advance(entry.key, expected_revision=1, now=101,
            transition=SimingAdmissionTransition(state='provider_pending', stage='candidate',
                provider=provider.model_copy(update={'pin_digest':'wrong'})))
    with pytest.raises(ValueError, match='expired'):
        api.advance(entry.key, expected_revision=1, now=200,
            transition=SimingAdmissionTransition(state='provider_pending', stage='candidate', provider=provider))
    stale = api.expire(entry.key, now=200)
    assert stale.entry.state == 'stale'
    assert api.list_pending(scope=scope()).entries == []
    graph.close()


def test_sqlite_failure_rolls_back_fact_idempotency_and_pending_index(tmp_path, monkeypatch):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    original = graph._update_admission_index
    def fail(node):
        original(node)
        raise OSError('index disk failure')
    monkeypatch.setattr(graph, '_update_admission_index', fail)
    with pytest.raises(OSError, match='disk'):
        api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1')
    for table in ['graph_nodes', 'graph_idempotency', 'graph_siming_pending']:
        assert graph._connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == 0
    monkeypatch.setattr(graph, '_update_admission_index', original)
    assert not api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').replayed
    graph.close()


def test_reopen_no_history_decode_and_explicit_index_rebuild(tmp_path, monkeypatch):
    from app.models.siming_heavenly_graph import HeavenlyGraphNode
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    entry = service(graph).admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    graph.close()
    def fail(*args, **kwargs):
        raise AssertionError('history scan')
    with monkeypatch.context() as patch:
        patch.setattr(HeavenlyGraphNode, 'model_validate_json', fail)
        patch.setattr(SQLiteHeavenlyGraphAdapter, '_rebuild_admission_index', fail)
        reopened = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    assert service(reopened).list_pending(scope=scope()).entries == [entry]
    reopened._connection.execute('DELETE FROM graph_siming_pending')
    reopened._connection.commit()
    reopened.rebuild_admission_index()
    assert service(reopened).list_pending(scope=scope()).entries == [entry]
    reopened.close()

@pytest.mark.parametrize('checkpoint', ['before_commit', 'after_commit', 'result_ready'])
def test_process_exit_recovery_keeps_atomic_admission_and_stage(tmp_path, checkpoint):
    import subprocess
    import sys
    import os
    path = tmp_path / 'crash.db'
    script = '''
import os, sys, hashlib
from app.services.sqlite_heavenly_graph import SQLiteHeavenlyGraphAdapter
from test_siming_admission import service, scope, prepared_provider
from test_siming_llm_runtime import make_visual_fact_event
from app.models.siming_heavenly_memory import SimingAdmissionTransition
from app.services.siming_continuation import SimingProviderCompletion
graph = SQLiteHeavenlyGraphAdapter(sys.argv[1])
api = service(graph)
if sys.argv[2] == 'before_commit':
    original = graph._update_admission_index
    def crash(node):
        original(node)
        os._exit(71)
    graph._update_admission_index = crash
entry = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
if sys.argv[2] == 'result_ready':
    provider = prepared_provider()
    api.advance(entry.key, expected_revision=1, now=101, transition=SimingAdmissionTransition(state='provider_pending', stage='candidate', provider=provider))
    completion = SimingProviderCompletion(request_digest=hashlib.sha256(provider.request_json.encode()).hexdigest())
    api.advance(entry.key, expected_revision=2, now=102, transition=SimingAdmissionTransition(state='result_ready', stage='candidate', completion_json=completion.model_dump_json()))
os._exit(71)
'''
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join(['backend', 'backend/tests'])}
    result = subprocess.run([sys.executable, '-c', script, str(path), checkpoint], env=env, capture_output=True, text=True)
    assert result.returncode == 71, result.stderr
    graph = SQLiteHeavenlyGraphAdapter(path)
    api = service(graph)
    page = api.list_pending(scope=scope())
    if checkpoint == 'before_commit':
        assert page.entries == []
        assert graph._connection.execute('SELECT COUNT(*) FROM graph_nodes').fetchone()[0] == 0
        assert graph._connection.execute('SELECT COUNT(*) FROM graph_idempotency').fetchone()[0] == 0
    else:
        assert len(page.entries) == 1
        assert page.entries[0].state == ('result_ready' if checkpoint == 'result_ready' else 'admitted')
    retry = api.admit(scope=scope(), source=make_visual_fact_event(), now=110, expires_at=210, policy_version='v1')
    assert retry.replayed == (checkpoint != 'before_commit')
    if checkpoint == 'result_ready':
        assert api.read(retry.entry.key, revision=2).entry.transition.provider is not None
        assert retry.entry.transition.completion_json is not None
    graph.close()


def test_admission_scope_separation_schema_validation_and_cursor_bounds(tmp_path):
    from pydantic import ValidationError
    from app.models.siming_heavenly_memory import SimingAdmissionProvider
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    a = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    other = scope().model_copy(update={'session_id':'other'})
    b = api.admit(scope=other, source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    assert a.entry_id != b.entry_id
    assert api.list_pending(scope=scope()).entries == [a]
    assert api.list_pending(scope=other).entries == [b]
    for limit in (0, -1, 257):
        with pytest.raises(ValueError, match='page_limit'):
            api.list_pending(scope=scope(), limit=limit)
    with pytest.raises(ValidationError):
        SimingAdmissionProvider.model_validate({**prepared_provider().model_dump(), 'schema_version':2})
    graph.close()


def test_operational_seed_does_not_enter_compiler_or_history(tmp_path):
    from app.services.siming_context_compiler import SimingContextCompiler
    from app.models.siming_heavenly_memory import SimingContextRequest
    for graph in [InMemoryHeavenlyGraphAdapter(), SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')]:
        entry = service(graph).admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
        compiled = SimingContextCompiler(graph).compile(SimingContextRequest(scope=scope(), valid_at=100, seed_node_ids=[entry.entry_id]))
        assert compiled.selected_node_refs == []
        assert compiled.intervention_outcomes == []
        assert graph.query_node_history(HeavenlyNodeQuery(scope=scope(), valid_at=100)) == []
        if isinstance(graph, SQLiteHeavenlyGraphAdapter):
            graph.close()


def test_effect_keys_are_stage_scoped_and_outstanding_plan_cannot_requeue(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition, SimingAdmissionEffect
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    entry = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    key = entry.key
    assert key.effect_key('adaptive', 0, 0) != key.effect_key('candidate', 0, 0)
    plan = SimingAdmissionTransition(state='commit_started', stage='initial', effects=[
        SimingAdmissionEffect(effect_key=key.effect_key('initial', 0, 0), kind='dispatch', payload={})])
    api.advance(key, expected_revision=1, transition=plan, now=101)
    with pytest.raises(ValueError, match='outstanding_effect'):
        api.advance(key, expected_revision=2, transition=SimingAdmissionTransition(state='requeued'), now=102)
    graph.close()


def test_admission_does_not_invalidate_real_adaptive_business_pin(adaptive_state):
    from test_siming_continuation import _adaptive_input
    from app.services.siming_continuation import run_siming_provider
    runtime = adaptive_state.siming_runtime
    item = _adaptive_input()
    pending = runtime.prepare_tick(item)
    service(adaptive_state.graph).admit(scope=adaptive_state.scope, source=item.source_event,
        now=100, expires_at=200, policy_version='v1')
    completion = run_siming_provider(runtime.heavenly_support._llm_provider, pending.job.request_json)
    outcome = runtime.commit_provider_result(pending.job, completion)
    assert outcome.status == 'completed'


from test_siming_continuation import adaptive_state


def test_effect_receipt_cannot_be_forgotten_on_next_commit_revision(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition, SimingAdmissionEffect, SimingAdmissionEffectReceipt
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    entry = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    effects = [SimingAdmissionEffect(effect_key=entry.key.effect_key('initial', 0, 0), kind='dispatch', payload={})]
    plan = SimingAdmissionTransition(state='commit_started', effects=effects)
    api.advance(entry.key, expected_revision=1, transition=plan, now=101)
    api.advance(entry.key, expected_revision=2, now=102, transition=plan.model_copy(update={
        'receipts':[SimingAdmissionEffectReceipt(effect_key=effects[0].effect_key, receipt={'event_id':'event:once'})]}))
    with pytest.raises(ValueError, match='receipt_conflict'):
        api.advance(entry.key, expected_revision=3, now=103, transition=plan)
    graph.close()


@pytest.mark.parametrize('sqlite', [False, True])
def test_operational_entry_rejects_business_causal_edges(tmp_path, sqlite):
    from app.models.siming_heavenly_graph import HeavenlyGraphRelation, HeavenlyGraphWriteBatch, GraphValidity, GraphProvenance
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db') if sqlite else InMemoryHeavenlyGraphAdapter()
    entry = service(graph).admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    relation = HeavenlyGraphRelation(relation_id='causal:bad', relation_type='CAUSED_BY', scope=scope(),
        source_node_id=entry.entry_id, target_node_id=entry.entry_id, validity=GraphValidity(valid_from=0),
        recorded_at=101, revision=1, provenance=GraphProvenance(source_kind='runtime_outcome', source_ref='source:1',
            causation_id='cause:1', correlation_id='correlation:1', producer_system='test'))
    with pytest.raises(ValueError, match='operational'):
        graph.write_batch(HeavenlyGraphWriteBatch(scope=scope(), transaction_id='tx:bad', idempotency_key='bad', relations=[relation]))
    if sqlite:
        graph.close()


@pytest.mark.parametrize('sqlite', [False, True])
def test_branch_fork_never_clones_operational_admission(tmp_path, sqlite):
    from app.models.siming_heavenly_graph import GraphBranchForkRequest
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db') if sqlite else InMemoryHeavenlyGraphAdapter()
    service(graph).admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1')
    graph.fork_branch(GraphBranchForkRequest(source_scope=scope(), target_branch_id='branch:preview',
        fork_valid_at=100, fork_recorded_at=100, source_revision_vector=graph.scope_revision_vector(scope())))
    target = scope().model_copy(update={'story_branch_id':'branch:preview'})
    assert service(graph).list_pending(scope=target).entries == []
    assert len(service(graph).list_pending(scope=scope()).entries) == 1
    if sqlite:
        graph.close()


def test_latest_receipt_has_exact_frozen_and_result_revision_anchors(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition
    from app.services.siming_continuation import SimingProviderCompletion
    import hashlib
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'g.db')
    api = service(graph)
    key = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry.key
    provider = prepared_provider()
    api.advance(key, expected_revision=1, now=101, transition=SimingAdmissionTransition(state='provider_pending', stage='candidate', provider=provider))
    completion = SimingProviderCompletion(request_digest=hashlib.sha256(provider.request_json.encode()).hexdigest()).model_dump_json()
    api.advance(key, expected_revision=2, now=102, transition=SimingAdmissionTransition(state='result_ready', stage='candidate', completion_json=completion))
    api.advance(key, expected_revision=3, now=103, transition=SimingAdmissionTransition(state='commit_started', stage='candidate'))
    latest = api.advance(key, expected_revision=4, now=104, transition=SimingAdmissionTransition(state='completed')).entry
    assert (latest.provider_revision, latest.result_revision, latest.commit_revision) == (2, 3, 4)
    assert api.read(key, revision=latest.provider_revision).entry.transition.provider == provider
    assert api.read(key, revision=latest.result_revision).entry.transition.completion_json == completion
    graph.close()


@pytest.mark.parametrize('sqlite', [False, True])
def test_pending_all_scopes_cursor_finds_later_rooms_after_reopen(tmp_path, sqlite):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'all.db') if sqlite else InMemoryHeavenlyGraphAdapter()
    api = service(graph)
    for index in range(1007):
        room = scope().model_copy(update={'room_id': f'room:{index % 3}', 'scene_id': f'scene:{index % 2}'})
        event = make_visual_fact_event().model_copy(update={'event_id': f'event:all:{index}'})
        api.admit(scope=room, source=event, now=100 + index % 2, expires_at=200, policy_version='v1')
    if sqlite:
        graph.close()
        graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'all.db')
        api = service(graph)
    seen, cursor = [], None
    while True:
        page = api.list_pending_all(limit=31, cursor=cursor)
        assert len(page.entries) <= 31
        seen.extend(entry.entry_id for entry in page.entries)
        cursor = page.next_cursor
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 1007
    if sqlite:
        graph.close()


@pytest.mark.parametrize('sqlite', [False, True])
def test_admission_room_sequence_shared_across_scene_and_clock_rollback(tmp_path, sqlite):
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'room.db') if sqlite else InMemoryHeavenlyGraphAdapter()
    api = service(graph)
    first_scope = scope().model_copy(update={'room_id': 'room:1', 'scene_id': 'scene:a'})
    second_scope = first_scope.model_copy(update={'scene_id': 'scene:b'})
    event = make_visual_fact_event()
    first = api.admit(scope=first_scope, source=event, now=100, expires_at=200, policy_version='v1')
    second = api.admit(scope=second_scope, source=event.model_copy(update={'event_id': 'earlier-hash'}), now=90, expires_at=200, policy_version='v1')
    assert [first.entry.room_sequence, second.entry.room_sequence] == [1, 2]
    assert api.admit(scope=first_scope, source=event, now=101, expires_at=200, policy_version='v1').entry.room_sequence == 1
    if sqlite:
        graph.close()
        graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'room.db')
        api = service(graph)
    assert api.read_room_head(first_scope).last_sequence == 2
    third = api.admit(scope=first_scope, source=event.model_copy(update={'event_id': 'third'}), now=80, expires_at=200, policy_version='v1')
    assert third.entry.room_sequence == 3
    if sqlite:
        graph.close()


def test_room_head_admission_atomic_rollback_and_reopen(tmp_path):
    import sqlite3
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'room-failure.db')
    api = service(graph)
    event = make_visual_fact_event()
    graph._connection.execute("CREATE TRIGGER fail_head BEFORE INSERT ON graph_siming_room_heads BEGIN SELECT RAISE(ABORT,'head failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='head failure'):
        api.admit(scope=scope(), source=event, now=100, expires_at=200, policy_version='v1')
    from app.models.siming_heavenly_memory import SimingAdmissionKey
    assert api.read(SimingAdmissionKey(scope=scope(), source_event_id=event.event_id)) is None
    assert api.read_room_head(scope()) is None
    assert api.list_pending_all().entries == []
    graph._connection.execute('DROP TRIGGER fail_head')
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'room-failure.db')
    api = service(graph)
    assert api.read_room_head(scope()) is None
    assert api.admit(scope=scope(), source=event, now=100, expires_at=200, policy_version='v1').entry.room_sequence == 1
    graph.close()


def test_room_prefix_follows_admission_order_not_due_time(tmp_path):
    from app.models.siming_heavenly_memory import SimingAdmissionTransition
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'prefix.db')
    api = service(graph)
    room = scope().model_copy(update={'room_id': 'room:prefix'})
    first = api.admit(scope=room.model_copy(update={'scene_id': 'a'}), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1')
    second = api.admit(scope=room.model_copy(update={'scene_id': 'b'}), source=make_visual_fact_event(), now=90, expires_at=200, policy_version='v1')
    assert api.read_room_pending(room).entry.key == first.entry.key
    api.advance(first.entry.key, expected_revision=1, transition=SimingAdmissionTransition(state='cancelled'), now=101)
    assert api.read_room_pending(room).entry.key == second.entry.key
    graph.close()


def test_room_index_migration_from_v4_and_failed_migration_rolls_back(tmp_path):
    import sqlite3
    path = tmp_path / 'v4.db'
    graph = SQLiteHeavenlyGraphAdapter(path)
    api = service(graph)
    api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1')
    graph.close()
    with sqlite3.connect(path) as connection:
        connection.execute('DROP TABLE graph_siming_room_heads')
        connection.execute('DROP TABLE graph_siming_pending')
        connection.execute('CREATE TABLE graph_siming_pending(scope_json TEXT NOT NULL, entry_id TEXT NOT NULL, revision INTEGER NOT NULL,state TEXT NOT NULL,due_at REAL NOT NULL,PRIMARY KEY(scope_json,entry_id))')
        connection.execute('UPDATE schema_version SET version=4')
        connection.execute("CREATE TRIGGER fail_migration BEFORE INSERT ON schema_version BEGIN SELECT RAISE(ABORT,'migration failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='migration failure'):
        SQLiteHeavenlyGraphAdapter(path)
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT version FROM schema_version').fetchone()[0] == 4
        assert len(list(connection.execute('PRAGMA table_info(graph_siming_pending)'))) == 5
        connection.execute('DROP TRIGGER fail_migration')
    graph = SQLiteHeavenlyGraphAdapter(path)
    assert service(graph).read_room_pending(scope()).entry.key.source_event_id == make_visual_fact_event().event_id
    assert len(service(graph).list_pending_all().entries) == 1
    with pytest.raises(ValueError, match='room_order_unavailable'):
        service(graph).admit(scope=scope(), source=make_visual_fact_event().model_copy(update={'event_id': 'new-after-v4'}),
                             now=101, expires_at=200, policy_version='v1')
    graph.close()


def test_room_after_state_and_admission_advance_are_atomic(tmp_path):
    import sqlite3
    from app.models.siming_heavenly_memory import SimingAdmissionTransition
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'after-state.db')
    api = service(graph)
    entry = api.admit(scope=scope(), source=make_visual_fact_event(), now=100, expires_at=200, policy_version='v1').entry
    head = api.read_room_head(scope())
    after = head.model_copy(update={'revision': 2, 'after_state': {'narrative': {'revision': 1, 'open_count': 1}}})
    transition = SimingAdmissionTransition(state='commit_started', room_head=after)
    graph._connection.execute("CREATE TRIGGER fail_after BEFORE UPDATE ON graph_siming_room_heads BEGIN SELECT RAISE(ABORT,'after failure'); END")
    with pytest.raises(sqlite3.IntegrityError, match='after failure'):
        api.advance(entry.key, expected_revision=1, transition=transition, now=101)
    assert api.read(entry.key).entry.revision == 1
    assert api.read_room_head(scope()) == head
    graph._connection.execute('DROP TRIGGER fail_after')
    receipt = api.advance(entry.key, expected_revision=1, transition=transition, now=101)
    assert api.read_room_head(scope()) == after
    assert api.advance(entry.key, expected_revision=1, transition=transition, now=102).replayed
    graph.close()
    graph = SQLiteHeavenlyGraphAdapter(tmp_path / 'after-state.db')
    assert service(graph).read(entry.key).entry == receipt.entry
    assert service(graph).read_room_head(scope()) == after
    graph.close()
