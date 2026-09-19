from copy import deepcopy

import pytest

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.runtime.session_recovery import reduce_session_event, session_event_facts
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from test_character_agent_seed_continuity import command_for_char_a


def test_compact_reducer_matches_full_runtime_replay(tmp_path):
    session = CharacterAgentSessionStore(tmp_path)
    state = None

    def append(kind, payload):
        nonlocal state
        event = session.append_event("char_a", kind, 11, payload)
        before = deepcopy(state)
        state = reduce_session_event(state, event)
        assert before is None or before["event_index"] + 1 == state["event_index"]

    for i in range(12):
        append("goal_state_event", {"primary_goal": f"goal:{i}"})
        append("character_unresolved_tension_event", {"tension_id": f"tension:{i}", "category": "test", "summary": "pressure", "priority": i / 12})
    append("dynamic_state_event", {"stress_load": .4, "vigilance_level": .3, "distraction_level": .1})
    append("need_tension_state_event", {"physiological_pressure": .4})
    append("character_supervision_authorization", {"approved_level": "medium", "approved_by": "strategy_service", "constraints": {"background_mode": "active"}, "effective_from_ts": 5, "producer_ts": 8})
    append("character_background_cognition_event", {"background_agenda_state": {"actor_id": "char_a", "agenda_summary": "continue"}})
    append("character_perceived_event", {"summary": "unbounded history must stay outside hot state"})
    session.close()
    oracle = CharacterAgentRuntime(storage_root=tmp_path)
    assert state["goal_history"] == oracle.get_goal_state_history("char_a")
    assert len(state["goal_history"]) == 8
    assert state["dynamic_state"] == oracle.get_dynamic_state_record("char_a").storage_dump()
    assert state["need_tension_state"] == oracle.get_need_tension_state("char_a")
    assert state["unresolved_tensions"] == oracle._unresolved_tension_store.recall("char_a")
    assert state["supervision_state"] == oracle._supervision_states["char_a"].model_dump(mode="json")
    assert state["background_agenda_state"] == oracle._background_agenda_states["char_a"].model_dump(mode="json")
    assert state["event_index"] == oracle.get_memory_revision("char_a")
    assert "session_timeline" not in state and "working_memory" not in state
    oracle._session_store.close()


def test_seed_reducer_preserves_exact_state_and_keeps_cold_fields_out():
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(command_for_char_a(state_delta={
        "need_tension": {"physiological_pressure": .4},
        "dynamic_state": {"stress_load": .6}, "activation_hints": ["food"],
    }))
    assert receipt.status == "committed"
    event = runtime.get_session_timeline("char_a")[0]
    state = reduce_session_event(None, event)
    assert state["continuity_revision"] == 1
    assert state["seed_event_id"] == event["event_id"]
    assert state["dynamic_state"] == runtime.get_dynamic_state_record("char_a").storage_dump()
    assert state["need_tension_state"] == runtime.get_need_tension_state("char_a")
    assert state["wake_up"] == runtime._wake_up_signals["char_a"]
    assert "pending_seed_candidates" not in state and "seed_projection" not in state
    assert "continuity_receipts" not in state
    receipts, candidates = session_event_facts(event)
    assert receipts == [("continuity", "continuity:char_a:101", receipt.model_dump(mode="json"))]
    assert [value["candidate_id"] for value in candidates] == ["memory:char_a:default"]
    runtime.materialize_pending_seed_memories(actor_id="char_a", producer_ts=102)
    materialized = runtime.get_session_timeline("char_a")[-1]
    materialization_receipts, candidates = session_event_facts(materialized)
    assert len(materialization_receipts) == 1 and materialization_receipts[0][0] == "materialization"
    assert candidates == []
    with pytest.raises(ValueError, match="session_recovery_gap"):
        reduce_session_event(state, event)


def test_reducer_rejects_wrong_actor_and_does_not_mutate_input():
    events = CharacterAgentSessionStore()
    first = events.append_event("char_a", "dynamic_state_event", 1, {"stress_load": .1, "vigilance_level": 0., "distraction_level": 0.})
    state = reduce_session_event(None, first)
    before = deepcopy(state)
    bad = events.append_event("char_a", "dynamic_state_event", 2, {"stress_load": "invalid"})
    with pytest.raises(ValueError):
        reduce_session_event(state, bad)
    assert state == before
    with pytest.raises(ValueError, match="session_recovery_actor_mismatch"):
        reduce_session_event(state, {**bad, "actor_id": "char_b"})


def test_ready_uses_compact_state_and_preserves_explicit_history(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    for index in range(25):
        runtime._append_session_event("char_a", "goal_state_event", index, {"primary_goal": f"goal:{index}"})
    before = runtime.get_session_timeline("char_a")
    runtime.close()
    original = CharacterAgentSessionStore.list_events_after
    monkeypatch.setattr(CharacterAgentSessionStore, "list_events", lambda *a, **k: pytest.fail("ready read full history"))
    monkeypatch.setattr(CharacterAgentSessionStore, "list_events_after", lambda *a, **k: pytest.fail("ready replayed full history"))
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    assert restored.get_goal_state("char_a")["primary_goal"] == "goal:24"
    assert len(restored.get_goal_state_history("char_a")) == 8
    assert restored.get_memory_revision("char_a") == 25
    monkeypatch.setattr(CharacterAgentSessionStore, "list_events_after", original)
    assert restored.get_session_timeline("char_a") == before
    restored.close()


def test_recovery_state_and_cold_facts_commit_atomically(tmp_path):
    store = CharacterAgentSessionStore(tmp_path)
    store.initialize_recovery()
    first = store.append_event("char_a", "goal_state_event", 1, {"primary_goal": "first"})
    store._connection.execute("CREATE TRIGGER reject_recovery BEFORE UPDATE ON character_session_recovery BEGIN SELECT RAISE(ABORT,'cut'); END")
    with pytest.raises(Exception, match="cut"):
        store.append_event("char_a", "goal_state_event", 2, {"primary_goal": "second"})
    assert store.event_count("char_a") == 1
    assert store.read_runtime_state("char_a")["event_id"] == first["event_id"]
    store.close()


def test_lost_sqlite_does_not_reimport_frozen_legacy(tmp_path):
    import json
    events = CharacterAgentSessionStore()
    first = events.append_event('char_a', 'probe', 1, {})
    (tmp_path / 'character_agent_session_store.json').write_text(json.dumps({'char_a':[first]}), encoding='utf-8')
    store = CharacterAgentSessionStore(tmp_path)
    store.append_event('char_a', 'probe', 2, {})
    store.close()
    (tmp_path / 'character_sessions.sqlite3').unlink()
    with pytest.raises(ValueError, match='archive_missing'):
        CharacterAgentSessionStore(tmp_path)


def test_imports_previous_separate_sqlite_without_frozen_json(tmp_path):
    root = tmp_path / 'local'
    old = CharacterAgentSessionStore(root)
    history = [old.append_event('char_a','probe',i,{'i':i}) for i in range(3)]
    old.close()
    (root / 'character_agent_session_store.json').write_text('broken backup',encoding='utf-8')
    new = CharacterAgentSessionStore(root, database_path=tmp_path/'graph.sqlite3')
    assert new.list_events('char_a') == history
    new.close()


def test_ask_persistence_deepcopy_is_detached_and_rollback_is_atomic(tmp_path, monkeypatch):
    from test_character_memory_consistency_flow import observation
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    runtime.record_character_perceived_event_without_cognition(observation())
    store = runtime._l1.get_actor_scene_knowledge_store()
    before = [v.model_dump(mode='json') for v in store.entries_for_actor('char_a')]
    trace = deepcopy(store.trace)
    clone = deepcopy(store)
    clone.mark_stale(before[0]['entry_id'],producer_ts=2)
    assert [v.model_dump(mode='json') for v in store.entries_for_actor('char_a')] == before
    assert store.trace == trace
    original = runtime._session_store.write_ask
    def cut(entry, item):
        original(entry,item)
        raise OSError('ASK cut')
    monkeypatch.setattr(runtime._session_store,'write_ask',cut)
    with pytest.raises(OSError,match='ASK cut'):
        runtime.record_character_perceived_event_without_cognition(observation(value='hidden',source='changed',at=3))
    assert [v.model_dump(mode='json') for v in store.entries_for_actor('char_a')] == before
    assert store.trace == trace
    assert runtime.get_memory_revision('char_a') == 2
    runtime.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    after = restored._l1.get_actor_scene_knowledge_store()
    assert len(after.trace) == len(trace)+1
    assert len(after.entries_for_actor('char_a')[0].revisions) == 2
    restored.close()


def test_non_event_dynamic_flush_survives_but_cannot_overwrite_newer_reducer(tmp_path):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    runtime._append_session_event('char_a','dynamic_state_event',1,{'stress_load':.2, 'vigilance_level':0., 'distraction_level':0.})
    runtime._dynamic_state_store.write('char_a', {'stress_load':.5, 'vigilance_level':0., 'distraction_level':0.})
    runtime._persist_graph_continuity(actor_id='char_a',producer_ts=2)
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    assert restored.get_dynamic_state_record('char_a').stress_load == .5
    restored.close()
    runtime._session_store.append_event('char_a','dynamic_state_event',3,{'stress_load':.9, 'vigilance_level':0., 'distraction_level':0.})
    runtime._persist_graph_continuity(actor_id='char_a',producer_ts=4)
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    assert restored.get_dynamic_state_record('char_a').stress_load == .9
    restored.close()
    runtime.close()


def test_ask_same_entry_id_keeps_distinct_scene_keys(tmp_path):
    from test_character_memory_consistency_flow import observation
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    runtime.record_character_perceived_event_without_cognition(observation())
    runtime.record_character_perceived_event_without_cognition(observation(source='room2',at=2).model_copy(update={'room_id':'room_other'}))
    entries = runtime._l1.get_actor_scene_knowledge_store().entries_for_actor('char_a')
    assert {value.session_id for value in entries} == {'room_demo','room_other'}
    runtime.close()


@pytest.mark.parametrize('damage', ['missing_current','missing_head','head_id','missing_cursor','missing_ask_table','schema_drift'])
def test_ready_fails_closed_on_missing_or_unknown_projection(tmp_path, damage):
    import sqlite3
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    runtime._append_session_event('char_a','probe',1,{})
    runtime.close()
    db = sqlite3.connect(tmp_path/'character_sessions.sqlite3')
    operations = {
        'missing_current':'DELETE FROM character_session_recovery',
        'missing_head':'DELETE FROM character_session_heads',
        'head_id':"UPDATE character_session_heads SET event_id='different'",
        'missing_cursor':'DELETE FROM character_session_projection_cursors',
        'missing_ask_table':'DROP TABLE character_session_ask',
        'schema_drift':"UPDATE character_session_metadata SET value='99' WHERE key='recovery_version'",
    }
    db.execute(operations[damage]); db.commit(); db.close()
    with pytest.raises(ValueError, match='recovery|projection'):
        CharacterAgentRuntime(storage_root=tmp_path)


def test_recovery_schema_upgrade_failure_rolls_back_all_derived_tables(tmp_path, monkeypatch):
    import sqlite3
    session = CharacterAgentSessionStore(tmp_path)
    history = [session.append_event('char_a','probe',i,{}) for i in range(3)]
    def cut(event):
        if event['event_index'] == 2:
            raise OSError('migration cut')
    with pytest.raises(OSError, match='migration cut'):
        session.initialize_recovery(project_event=cut)
    db = session._connection
    assert db.execute("SELECT name FROM sqlite_master WHERE name='character_session_recovery'").fetchone() is None
    assert db.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone() is None
    assert session.list_events('char_a') == history
    assert session.initialize_recovery()
    assert session.read_runtime_state('char_a')['event_index'] == 3
    session.close()


@pytest.mark.parametrize('damage', ['actor','payload','index','anchor','cursor','current_cursor'])
def test_legacy_graph_import_rejects_divergent_or_unanchored_history(tmp_path, damage):
    session = CharacterAgentSessionStore(tmp_path)
    first = session.append_event('char_a','probe',1,{'v':1})
    checkpoint = {'session_timeline':[deepcopy(first)],'checkpoint_event_index':1,
                  '_continuity_source_event_ref':first['event_id']}
    current = {}
    if damage == 'actor': checkpoint['session_timeline'][0]['actor_id'] = 'char_b'
    if damage == 'payload': checkpoint['session_timeline'][0]['payload'] = {'v':2}
    if damage == 'index': checkpoint['session_timeline'][0]['event_index'] = 2
    if damage == 'anchor': checkpoint['_continuity_source_event_ref'] = 'missing'
    if damage == 'cursor': checkpoint['checkpoint_event_index'] = 2
    if damage == 'current_cursor': current = {'session_timeline_tail':[], 'checkpoint_event_index':2, '_continuity_source_event_ref':first['event_id']}
    with pytest.raises(ValueError, match='continuity'):
        session.initialize_recovery(import_legacy=lambda: session.merge_legacy_continuity('char_a',checkpoint,current))
    assert session.list_events('char_a') == [first]
    session.close()


def test_legacy_graph_import_merges_complete_prefix_once(tmp_path):
    class Legacy:
        def read_snapshot(self, actor):
            return checkpoint if actor == 'char_a' else None
        def read_current_state(self, actor):
            return current if actor == 'char_a' else None
    source = CharacterAgentSessionStore()
    events = [source.append_event('char_a','goal_state_event',i,{'primary_goal':str(i)}) for i in range(12)]
    checkpoint = {'session_timeline':events[:8], 'checkpoint_event_index':8,
                  '_continuity_source_event_ref':events[7]['event_id']}
    current = {'session_timeline_tail':events[8:],'checkpoint_event_index':8,
               '_continuity_source_event_ref':events[-1]['event_id']}
    local = CharacterAgentSessionStore(tmp_path)
    with local.transaction(): local.import_timeline('char_a',events[:10])
    local.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path, continuity_store=Legacy())
    assert restored.get_session_timeline('char_a') == events
    assert [g['primary_goal'] for g in restored.get_goal_state_history('char_a')] == [str(i) for i in range(4,12)]
    restored.close()

    Legacy.read_snapshot = lambda *a: pytest.fail('migration ran twice')
    restored = CharacterAgentRuntime(storage_root=tmp_path, continuity_store=Legacy())
    assert restored.get_memory_revision('char_a') == 12
    restored.close()


@pytest.mark.parametrize('history_count', [1000,10000])
def test_large_history_ready_decodes_only_current_and_exact_head(tmp_path, monkeypatch, history_count):
    import json
    import app.character_agent.storage.session_store as module
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    for index in range(history_count):
        kind = ('character_perceived_event','character_agent_settlement_result','siming_output_event')[index % 3]
        runtime._append_session_event('char_a',kind,index,{'summary':'history', 'result_type':'ok'})
    runtime.close()
    decoded = []
    loads = json.loads
    def count_loads(value,*args,**kwargs):
        decoded.append(len(value.encode('utf-8')))
        return loads(value,*args,**kwargs)
    with monkeypatch.context() as scope:
        scope.setattr(module.json,'loads',count_loads)
        scope.setattr(CharacterAgentSessionStore,'list_events',lambda *a: pytest.fail('ready loaded history'))
        scope.setattr(CharacterAgentSessionStore,'list_events_after',lambda *a: pytest.fail('ready loaded history'))
        scope.setattr(CharacterAgentSessionStore,'read_ask',lambda *a,**k: pytest.fail('ready loaded ASK history'))
        scope.setattr(CharacterAgentSessionStore,'list_candidates',lambda *a: pytest.fail('ready loaded candidates'))
        restored = CharacterAgentRuntime(storage_root=tmp_path)
        assert restored.get_memory_revision('char_a') == history_count
        assert len(decoded) == 2
        assert sum(decoded) < 1000
    # 构造器绑定的是精确 session reader；显式全读取在计量结束后独立验证。
    restored._memory_store.bind_session_reader(restored._session_store.list_events)
    memory = restored.get_working_memory_state('char_a')
    assert sum(len(memory[field]) for field in ('recent_perceived_events','recent_esm_results','recent_siming_catalysts')) == history_count
    restored.close()


def test_light_heavy_full_memory_and_ask_equal_unbound_replay(tmp_path, monkeypatch):
    from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
    from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeStore
    from app import main
    from app.config import Settings
    from test_character_memory_consistency_flow import observation
    settings = Settings(heavenly_graph_path=str(tmp_path/'graph.sqlite3'),siming_heavenly_mode='off')
    owner = main.build_runtime_state(settings)
    runtime = owner.character_agent_runtime
    for actor in ('char_a','char_b'):
        for index in range(12):
            runtime.record_character_perceived_event_without_cognition(observation(
                value='hidden' if index % 2 else 'visible', source=f'{actor}:{index}', at=index+1).model_copy(update={'actor_id':actor}))
            runtime._append_session_event(actor,'character_agent_settlement_result',index+1,{'result_type':'ok','change_summary':str(index)})
    timelines = {actor:runtime.get_session_timeline(actor) for actor in ('char_a','char_b')}
    records = {actor:runtime.get_memory_record_bundle(actor).model_dump(mode='json') for actor in timelines}
    expected_ask = [entry.model_dump(mode='json') for actor in timelines for entry in runtime._l1.get_actor_scene_knowledge_store().entries_for_actor(actor)]
    expected_trace = runtime._l1.get_actor_scene_knowledge_store().trace
    owner.close()

    with monkeypatch.context() as scope:
        scope.setattr(CharacterAgentSessionStore,'read_ask',lambda *a,**k: pytest.fail('ready loaded ASK'))
        owner = main.build_runtime_state(settings)
    restored = owner.character_agent_runtime
    for actor,events in timelines.items():
        oracle = CharacterAgentMemoryStore()
        for event in events: oracle.write_event(event)
        snapshot = {'snapshot':'original'}
        dynamic = restored.get_dynamic_state_record(actor)
        assert restored.get_working_memory_state_record(actor,snapshot) == oracle.working_memory_state(actor,snapshot,dynamic)
        assert restored.get_memory_record_bundle(actor).model_dump(mode='json') == records[actor]
        assert restored.get_session_timeline(actor) == events
    actual_store = restored._l1.get_actor_scene_knowledge_store()
    assert [entry.model_dump(mode='json') for actor in timelines for entry in actual_store.entries_for_actor(actor)] == expected_ask
    assert actual_store.trace == expected_trace
    reference = CharacterAgentRuntime()
    reference._l1._ask_store = ActorSceneKnowledgeStore()
    for actor,events in timelines.items():
        for event in events: reference._update_memory_scene_knowledge_unchecked(event)
    assert [entry.model_dump(mode='json') for actor in timelines for entry in reference._l1.get_actor_scene_knowledge_store().entries_for_actor(actor)] == expected_ask
    reference.close()
    owner.close()


@pytest.mark.parametrize('table', ['events','heads','recovery','receipts','candidates'])
def test_seed_transaction_failure_cuts_leave_no_committed_fact(tmp_path, table):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    db = runtime._session_store._connection
    db.execute(f"CREATE TRIGGER cut BEFORE INSERT ON character_session_{table} BEGIN SELECT RAISE(ABORT,'atomic cut'); END")
    command = command_for_char_a()
    with pytest.raises(Exception, match='atomic cut'):
        runtime.apply_character_continuity_command(command)
    assert runtime.get_memory_revision('char_a') == 0
    assert runtime.get_continuity_revision('char_a') == 0
    assert runtime._session_store.read_runtime_state('char_a') is None
    assert runtime._session_store.read_receipt('char_a',kind='continuity',key=command.idempotency_key) is None
    assert runtime.get_pending_seed_candidates('char_a') == []
    db.execute('DROP TRIGGER cut')
    assert runtime.apply_character_continuity_command(command).status == 'committed'
    runtime.close()


def test_process_crash_after_commit_recovers_exact_retry(tmp_path):
    import os
    from pathlib import Path
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    environment = {**os.environ, 'PYTHONPATH':os.pathsep.join((str(root/'backend'),str(root/'backend/tests'))),
                   'PARALLS_HEAVENLY_GRAPH_PATH':':memory:', 'PYTHONUTF8':'1'}
    script = '''
import os, sys
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from test_character_agent_seed_continuity import command_for_char_a
runtime = CharacterAgentRuntime(storage_root=sys.argv[1])
runtime._memory_store.write_event = lambda event: os._exit(17)
runtime.apply_character_continuity_command(command_for_char_a())
'''
    first = subprocess.run([sys.executable,'-c',script,str(tmp_path)],cwd=root,env=environment,capture_output=True,text=True)
    assert first.returncode == 17, first.stderr
    script = '''
import sys
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from test_character_agent_seed_continuity import command_for_char_a
runtime = CharacterAgentRuntime(storage_root=sys.argv[1])
assert runtime.get_memory_revision('char_a') == 1
assert runtime.get_continuity_revision('char_a') == 1
assert runtime.apply_character_continuity_command(command_for_char_a()).status == 'idempotent_replay'
assert runtime.get_memory_revision('char_a') == 1
assert len(runtime.get_pending_seed_candidates('char_a')) == 1
runtime.close()
'''
    second = subprocess.run([sys.executable,'-c',script,str(tmp_path)],cwd=root,env=environment,capture_output=True,text=True)
    assert second.returncode == 0, second.stderr


def test_every_runtime_append_uses_single_transaction_entrypoint():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(CharacterAgentRuntime))
    calls = [node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)]
    direct = [node for node in calls if node.func.attr == 'append_event']
    routed = [node for node in calls if node.func.attr == '_append_session_event']
    assert len(direct) == 1
    # 四类认知写回统一由计划循环提交，原四处 append 收敛成一处。
    assert len(routed) == 28
    planner = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                   and node.name == '_plan_cognition_update')
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr in {'append_event', '_append_session_event'} for node in ast.walk(planner))


def test_old_receipt_exact_retry_rejects_changed_command_after_restart(tmp_path, monkeypatch):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    command = command_for_char_a()
    runtime.apply_character_continuity_command(command)
    runtime.materialize_pending_seed_memories('char_a',producer_ts=102)
    for i in range(100): runtime._append_session_event('char_a','probe',i,{})
    runtime.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    with monkeypatch.context() as scope:
        scope.setattr(restored._session_store,'list_events',lambda *a: pytest.fail('exact retry scanned history'))
        assert restored.apply_character_continuity_command(command).status == 'idempotent_replay'
        assert restored.apply_character_continuity_command(command.model_copy(update={'expected_character_revision':1})).status == 'idempotent_replay'
        with pytest.raises(ValueError,match='conflict'):
            restored.apply_character_continuity_command(command.model_copy(update={'state_delta':{'dynamic_state':{'stress_load':.9}}}))
        assert restored.materialize_pending_seed_memories('char_a',producer_ts=300)[0].status == 'idempotent_replay'
    assert restored.get_memory_revision('char_a') == 102
    assert len(restored.get_pending_seed_candidates('char_a')) == 1
    restored.close()


def test_in_memory_explicit_archive_supports_new_runtime_handoff():
    from app.character_agent.storage.graph_continuity_store import CharacterGraphContinuityStore
    from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
    from test_character_graph_continuity_store import _scope
    store = CharacterGraphContinuityStore(InMemoryHeavenlyGraphAdapter(),scope_resolver=_scope)
    first = CharacterAgentRuntime(continuity_store=store)
    first.apply_character_continuity_command(command_for_char_a())
    second = CharacterAgentRuntime(continuity_store=store)
    assert second.get_session_timeline('char_a') == first.get_session_timeline('char_a')
    assert second.get_continuity_revision('char_a') == 1
    second.close(); first.close()


@pytest.mark.parametrize('field', ['continuity_receipts','pending_seed_candidates'])
def test_legacy_receipt_and_candidate_payload_must_match_committed_event(tmp_path,field):
    source = CharacterAgentRuntime()
    source.apply_character_continuity_command(command_for_char_a())
    checkpoint = source._export_continuity_snapshot('char_a')
    value = next(iter(checkpoint[field].values()))
    if field == 'continuity_receipts': value['actor_ref'] = 'character:char_b'
    else: value['summary'] = 'forged candidate'
    class Legacy:
        def read_snapshot(self, actor): return checkpoint if actor == 'char_a' else None
        def read_current_state(self, actor): return None
    with pytest.raises(ValueError,match='continuity'):
        CharacterAgentRuntime(storage_root=tmp_path,continuity_store=Legacy())
    source.close()


def test_committed_goal_remains_visible_when_memory_projection_fails(tmp_path, monkeypatch):
    from app.models.character_agent_runtime import CharacterIntentDecision
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    monkeypatch.setattr(runtime._memory_store,'write_event',lambda event: (_ for _ in ()).throw(OSError('projection cut')))
    with pytest.raises(OSError,match='projection cut'):
        runtime._record_goal_state_event('char_a',1,CharacterIntentDecision(actor_id='char_a',selected_intent='observe',
            persona_passed=True,logic_passed=True,gain_loss_passed=True,rationale='observe',primary_goal='committed goal'))
    assert runtime.get_goal_state('char_a')['primary_goal'] == 'committed goal'
    assert len(runtime.get_goal_state_history('char_a')) == 1
    runtime.close()


def test_relocated_marker_cannot_fall_back_to_frozen_legacy(tmp_path):
    import shutil
    source = tmp_path / 'source'
    original = CharacterAgentSessionStore(source / 'local', database_path=source / 'graph.sqlite3')
    original.append_event('char_a','probe',1,{})
    original.close()
    clone = tmp_path / 'clone'
    shutil.copytree(source, clone)
    (clone / 'graph.sqlite3').unlink()
    # 原路径仍存在，也不能被当作 clone 的事实权威或首次初始化证据。
    with pytest.raises(ValueError, match='archive_missing'):
        CharacterAgentSessionStore(clone / 'local', database_path=clone / 'graph.sqlite3')


def test_legacy_non_event_dynamic_only_overlays_its_exact_head(tmp_path):
    source = CharacterAgentRuntime()
    source._append_session_event('char_a','dynamic_state_event',1,{'stress_load':.2,'vigilance_level':0.,'distraction_level':0.})
    source._dynamic_state_store.write('char_a', {'stress_load':.6,'vigilance_level':0.,'distraction_level':0.})
    checkpoint = source._export_continuity_snapshot('char_a')
    checkpoint['dynamic_state'] = source.get_dynamic_state_record('char_a').storage_dump()
    class Legacy:
        def read_snapshot(self, actor): return checkpoint if actor == 'char_a' else None
        def read_current_state(self, actor): return None
    restored = CharacterAgentRuntime(storage_root=tmp_path/'same',continuity_store=Legacy())
    assert restored.get_dynamic_state_record('char_a').stress_load == .6
    restored.close()
    later = CharacterAgentSessionStore(tmp_path/'later')
    later.import_timeline('char_a',source.get_session_timeline('char_a'))
    later._connection.commit()
    later.append_event('char_a','dynamic_state_event',2,{'stress_load':.9,'vigilance_level':0.,'distraction_level':0.})
    later.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path/'later',continuity_store=Legacy())
    assert restored.get_dynamic_state_record('char_a').stress_load == .9
    restored.close(); source.close()


def test_invalid_legacy_current_model_rolls_back_migration(tmp_path):
    import sqlite3
    source = CharacterAgentRuntime()
    source._append_session_event('char_a','probe',1,{})
    checkpoint = source._export_continuity_snapshot('char_a')
    checkpoint['supervision_state'] = {'actor_id':'char_a','current_level':'invalid'}
    class Legacy:
        def read_snapshot(self, actor): return checkpoint if actor == 'char_a' else None
        def read_current_state(self, actor): return None
    with pytest.raises(ValueError):
        CharacterAgentRuntime(storage_root=tmp_path,continuity_store=Legacy())
    with sqlite3.connect(tmp_path/'character_sessions.sqlite3') as db:
        assert db.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone() is None
        assert db.execute("SELECT COUNT(*) FROM character_session_events").fetchone()[0] == 0
    source.close()


@pytest.mark.parametrize('field', ['dynamic_state', 'supervision_state'])
def test_dialogue_append_does_not_claim_uninstalled_field_version(tmp_path, field):
    from app.character_agent.models.supervision import CharacterSupervisionState
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    if field == 'dynamic_state':
        kind = 'dynamic_state_event'
        initial = {'stress_load':.2,'vigilance_level':0.,'distraction_level':0.}
        newer = {**initial,'stress_load':.9}
    else:
        kind = 'character_supervision_cleared'
        initial = CharacterSupervisionState(actor_id='char_a',last_reason_summary='old').model_dump(mode='json')
        newer = {**initial,'last_reason_summary':'newer'}
    runtime._append_session_event('char_a',kind,1,initial)
    runtime._install_recovery_state('char_a')
    runtime._session_store.append_event('char_a',kind,2,newer)
    expected = runtime._session_store.read_runtime_state('char_a')[field]
    runtime.record_dialogue_response(actor_id='char_a',producer_ts=3,payload={'content':'hello'})
    runtime._persist_graph_continuity(actor_id='char_a',producer_ts=4)
    assert runtime._session_store.read_runtime_state('char_a')[field] == expected
    runtime.close()
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    actual = (restored.get_dynamic_state_record('char_a').storage_dump() if field == 'dynamic_state'
              else restored._supervision_states['char_a'].model_dump(mode='json'))
    assert actual == expected
    restored.close()


@pytest.mark.parametrize('anchor', ['', 'nonexistent-anchor'])
def test_legacy_current_missing_source_rolls_back_and_can_retry(tmp_path, anchor):
    import sqlite3
    source = CharacterAgentSessionStore()
    events = [source.append_event('char_a','goal_state_event',i,{'primary_goal':str(i)}) for i in (1,2)]
    checkpoint = {'session_timeline':events[:1],'checkpoint_event_index':1,
                  '_continuity_source_event_ref':events[0]['event_id']}
    current = {'session_timeline_tail':events[1:],'checkpoint_event_index':1,
               '_continuity_source_event_ref':anchor}
    class Legacy:
        def read_snapshot(self, actor): return checkpoint if actor == 'char_a' else None
        def read_current_state(self, actor): return current if actor == 'char_a' else None
    with pytest.raises(ValueError,match='continuity_anchor'):
        CharacterAgentRuntime(storage_root=tmp_path,continuity_store=Legacy())
    with sqlite3.connect(tmp_path/'character_sessions.sqlite3') as db:
        assert db.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone() is None
        assert db.execute('SELECT COUNT(*) FROM character_session_events').fetchone()[0] == 0
        assert db.execute("SELECT name FROM sqlite_master WHERE name='character_session_recovery'").fetchone() is None
    current['_continuity_source_event_ref'] = events[-1]['event_id']
    restored = CharacterAgentRuntime(storage_root=tmp_path,continuity_store=Legacy())
    assert restored.get_session_timeline('char_a') == events
    restored.close(); source.close()


def test_schema_one_cross_database_migration_is_atomic_and_keeps_source_read_only(tmp_path, monkeypatch):
    import json
    import sqlite3
    root = tmp_path/'legacy'
    root.mkdir()
    source = root/'character_sessions.sqlite3'
    target = tmp_path/'graph.sqlite3'
    memory = CharacterAgentSessionStore()
    events = [memory.append_event('char_a','probe',i,{}) for i in (1,2)]
    memory.close()
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE character_session_metadata (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        db.execute("INSERT INTO character_session_metadata VALUES ('schema_version','1')")
        db.execute('CREATE TABLE character_session_events (actor_id TEXT NOT NULL,event_index INTEGER NOT NULL CHECK(event_index>0),event_id TEXT NOT NULL UNIQUE,event_type TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(actor_id,event_index))')
        db.execute('CREATE INDEX character_session_event_types ON character_session_events(actor_id,event_type,event_index)')
        db.execute('CREATE TABLE character_session_heads (actor_id TEXT PRIMARY KEY,event_count INTEGER NOT NULL CHECK(event_count>0),event_id TEXT NOT NULL)')
        for event in events:
            db.execute('INSERT INTO character_session_events VALUES (?,?,?,?,?)',('char_a',event['event_index'],event['event_id'],'probe',json.dumps(event)))
        db.execute('INSERT INTO character_session_heads VALUES (?,?,?)',('char_a',2,events[-1]['event_id']))
    original_bytes = source.read_bytes()
    original_insert = CharacterAgentSessionStore._insert_event
    def cut(db, event):
        original_insert(db,event)
        if event['event_index'] == 2:
            raise OSError('schema one migration cut')
    with monkeypatch.context() as scope:
        scope.setattr(CharacterAgentSessionStore,'_insert_event',staticmethod(cut))
        with pytest.raises(OSError,match='migration cut'):
            CharacterAgentSessionStore(root,database_path=target)
    assert source.read_bytes() == original_bytes
    with sqlite3.connect(target) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE name LIKE 'character_session_%'").fetchall() == []
    restored = CharacterAgentSessionStore(root,database_path=target)
    assert restored.list_events('char_a') == events
    assert restored._connection.execute("SELECT value FROM character_session_metadata WHERE key='schema_version'").fetchone() == ('2',)
    # 目的库采用 actor 内唯一 ID，不能照搬 schema 1 的全局 UNIQUE。
    with restored.transaction():
        restored.import_timeline('char_b',[{**events[0],'actor_id':'char_b'}])
    assert restored.read_event('char_b',event_id=events[0]['event_id'])['actor_id'] == 'char_b'
    restored.close()
    assert source.read_bytes() == original_bytes


@pytest.mark.parametrize('supersedes', ['seed:old', None, ''])
def test_legacy_receipt_compares_normalized_supersedes(tmp_path, supersedes):
    import json
    source = CharacterAgentRuntime()
    original = command_for_char_a(state_delta={'supersedes':'seed:fallback'})
    command = original.model_copy(update={'exposure_evidence':{**original.exposure_evidence,'supersedes':supersedes}})
    source.apply_character_continuity_command(command)
    events = source.get_session_timeline('char_a')
    del events[0]['payload']['continuity_commit']['command_digest']
    source.close()
    (tmp_path/'character_agent_session_store.json').write_text(json.dumps({'char_a':events}),encoding='utf-8')
    restored = CharacterAgentRuntime(storage_root=tmp_path)
    assert restored.apply_character_continuity_command(command.model_copy(update={'expected_character_revision':1})).status == 'idempotent_replay'
    changed = command.model_copy(update={'exposure_evidence':{**command.exposure_evidence,'supersedes':'seed:different'}})
    with pytest.raises(ValueError,match='command_conflict'):
        restored.apply_character_continuity_command(changed)
    assert restored.get_memory_revision('char_a') == 1
    restored.close()


@pytest.mark.parametrize("producer_fields", [{}, {"producer_ts": 0}, {"producer_ts": 1200}])
def test_supervision_refresh_timestamp_survives_reducer_flush_and_reopen(tmp_path, producer_fields):
    runtime = CharacterAgentRuntime(storage_root=tmp_path)
    authorization = {
        "authorization_id": "auth:refresh-fallback",
        "actor_id": "char_a",
        "approved_level": "medium",
        "approved_by": "strategy_service",
        "approval_reason": "timestamp continuity",
        "constraints": {},
        "effective_from_ts": 1234,
        **producer_fields,
    }
    expected = producer_fields.get("producer_ts") or 1234
    try:
        returned = runtime.apply_supervision_authorization(authorization)
        assert returned.last_refresh_ts == expected
        assert runtime.get_supervision_state("char_a")["last_refresh_ts"] == expected
        runtime._persist_graph_continuity(actor_id="char_a", producer_ts=1235)
        saved = runtime._session_store.read_runtime_state("char_a")
        assert saved["supervision_state"]["last_refresh_ts"] == expected
    finally:
        runtime.close()

    reopened = CharacterAgentRuntime(storage_root=tmp_path)
    try:
        assert reopened.get_supervision_state("char_a")["last_refresh_ts"] == expected
    finally:
        reopened.close()
