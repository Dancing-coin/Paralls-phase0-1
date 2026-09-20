"""恢复证据的合成拒绝测试；不冒充真实 1000/10000 窗冷恢复。"""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.verification import verify_population_long_session_recovery as gate


def _raw_sample(*, identity=1):
    ready = dict(restore_ms=20.,owner_restore_ms=15.,process_peak_rss_bytes=1024,
        parent_peak_rss_bytes=256,owner_peak_rss_bytes=768,rss_scope='sum_of_parent_and_owner_startup_peaks',
        parent_pid=identity,owner_pid=identity+1000,phase_ms={"restore":20.},calls={"decode:state":2},
        sql=dict(vm_interval=100,vm_steps_are_sampled=True,databases={"db":dict(rows=10,payload_bytes=1000,vm_steps_sampled=100)}),
        replayed_windows=[8],publisher_record_cache=[2])
    parent=dict(schema_version=1,pid=identity,started_ns=identity*1_000_000_000,
        marker_ns=identity*1_000_000_000+100_000_000,exit_ns=identity*1_000_000_000+200_000_000,
        exit_code=0,error=None,marker="POPULATION_READY "+json.dumps(ready),database_names={"db":"graph.sqlite3"})
    ready["caches"]=dict(graph={k:0 for k in ("_nodes","_relations","_idempotency","_checkpoints","_branch_markers")},
        gameplay={k:0 for k in ("_events","_transactions","_outbox")},session_events=0,light_memory_events=0,
        heavy_normalizer_events=0,population_receipts=2,population_fingerprints=2,
        activation_receipts=0,activation_history={key:0 for key in ("state","source_revision_vector","applied_event_ids")})
    expected=dict(value="unchanged",pending=dict(outbox={},projection_refresh={}))
    return dict(ready=ready,oracle=deepcopy(expected),verification_ms=50.,
        runtime_process=dict(parent_pid=identity,owner_pid=identity+1000,exit_code=0)),parent,expected


def test_recovery_evidence_requires_original_owner_exit_and_both_memory_peaks():
    for field, value in [('owner_pid', 1), ('parent_pid', 99), ('owner_peak_rss_bytes', 0),
            ('parent_peak_rss_bytes', 0), ('process_peak_rss_bytes', 768), ('owner_restore_ms', 21.),
            ('rss_scope', 'parent_only')]:
        child, parent, expected = _raw_sample()
        child['ready'][field] = value
        parent['marker'] = 'POPULATION_READY ' + json.dumps({k: v for k, v in child['ready'].items() if k != 'caches'})
        with pytest.raises(ValueError, match='recovery_process'):
            gate._measurement(child, parent, expected)
    for field, value in [('owner_pid', 99), ('parent_pid', 99), ('exit_code', None), ('exit_code', False), ('exit_code', 1)]:
        child, parent, expected = _raw_sample()
        child['runtime_process'][field] = value
        with pytest.raises(ValueError, match='recovery_process'):
            gate._measurement(child, parent, expected)


@pytest.mark.parametrize("fault",[None,"marker","negative","nan","exit","timeout","timing","rows","cache","oracle"])
def test_parent_marker_and_raw_counters_determine_recovery_result(fault):
    child,parent,expected=_raw_sample()
    if fault=="marker": parent["marker"]="POPULATION_READY {}"
    if fault=="negative": child["verification_ms"]=-1
    if fault=="nan": child["verification_ms"]=float("nan")
    if fault=="exit": parent["exit_code"]=1
    if fault=="timeout": parent["error"]="TimeoutError"
    if fault=="timing": parent["marker_ns"]=parent["started_ns"]
    if fault=="rows":
        child["ready"]["sql"]["databases"]["db"]["rows"]=-1
        parent["marker"]="POPULATION_READY "+json.dumps({k:v for k,v in child["ready"].items() if k!="caches"})
    if fault=="cache": child["ready"]["caches"]["session_events"]=10000
    if fault=="oracle": child["oracle"]["value"]="changed"
    if fault in {None,"oracle"}:
        sample=gate._measurement(child,parent,expected)
        assert sample["ready"]["spawn_to_ready_ms"]==100
        assert sample["oracle_matches"]==(fault is None)
    else:
        with pytest.raises(ValueError): gate._measurement(child,parent,expected)


def test_formal_gate_recomputes_history_ratio_resources_and_configuration():
    cases={h:[gate._measurement(*_raw_sample(identity=i+1)) for i in range(5)] for h in (1000,10000)}
    assert gate._summary(cases,population=1000,tail=8,repeats=5)["passed"]
    assert not gate._summary(cases,population=100,tail=8,repeats=5)["passed"]
    changed=deepcopy(cases)
    changed[10000][0]["ready"]["calls"]["CharacterAgentSessionStore.list_events"]=1
    assert not gate._summary(changed,population=1000,tail=8,repeats=5)["passed"]
    changed=deepcopy(cases)
    for sample in changed[10000]: sample["ready"]["spawn_to_ready_ms"]=200
    assert not gate._summary(changed,population=1000,tail=8,repeats=5)["passed"]


def _evidence(directory,monkeypatch):
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    from test_population_durable_cadence_recovery import _runtime,_publisher
    identity=dict(base_commit="a"*40,source=dict(source_sha256="controlled",files={}))
    monkeypatch.setattr(gate,"_source_identity",lambda:identity)
    monkeypatch.setattr(gate,"implementation_digest",lambda _:"controlled-code")
    config=dict(population=2,histories=[16,32],tail=8,repeats=1)
    samples=[dict(history=h,repeat=0) for h in config["histories"]]
    cases={h:[] for h in config["histories"]}
    for index,h in enumerate(config["histories"]):
        fixture=directory/f"fixtures/{h}"; fixture.mkdir(parents=True)
        world=_runtime(directory/f"world-{h}.sqlite3",actors=("char_a","char_b"))
        cadence=world.build_population_cadence(window_start=0,window_end=(h+8)*86400)
        assert _publisher(world,InMemoryAuthorityEventBus())(cadence) is not None
        actor_fields=("dynamic","need","goal","goal_history","unresolved_tensions","supervision","agenda","continuity",
            "seed_projection","old_continuity_receipt","working_memory","knowledge")
        actors={a:{**{k:{} for k in actor_fields},"session_count":h+8,"session_head":"head","continuity_revision":1,
            **{k:"sha256:"+"a"*64 for k in ("session_digest","candidates_digest","memory_bundle_digest")}} for a in ("char_a","char_b")}
        from app.character_agent.storage.session_store import CharacterAgentSessionStore
        from scripts.verification.population_ask_audit import write_audit
        ask = CharacterAgentSessionStore(database_path=directory / f'ask-{h}.db')
        ask.initialize_recovery()
        from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeStore
        from test_ask_normalized_history import incoming
        knowledge = ActorSceneKnowledgeStore()
        knowledge.bind_persistence(ask)
        for actor in actors:
            for ordinal in range(4):
                knowledge.record(incoming(ordinal).model_copy(update={'actor_id': actor}), producer_ts=ordinal)
            actors[actor]['knowledge'] = write_audit(ask, actor, fixture / gate.ask_audit_name(actor))
        ask.close()
        oracle=dict(population=world.export_recovery_state(),confirmed_tick=(h+8)*86400,actors=actors,
            authority_digest="sha256:"+"a"*64,authority_events=h+8,pending=dict(outbox={},projection_refresh={}),
            stream_heads={"world":1},behavior_turns={str(i):{} for i in range(4)},inventory={},old_cadence=dict(committed=True))
        gate.write_json(fixture/"roster.json",dict(actor_ids=["char_a","char_b"]))
        metadata=dict(**identity,schema_version=2,implementation_digest="controlled-code",population=2,prefix_windows=h,
            tail_windows=8,active_private_history_actors=["char_a","char_b"],runtime_profile="production",window_size=86400,
            roster_sha256=gate.file_digest((fixture/"roster.json").read_bytes()),pending_before=oracle["pending"],
            actor_session_counts={a:h+8 for a in actors},graph_history_rows={name:2*(h+8) for name in (
                "graph_nodes","graph_relations","graph_idempotency","character_session_events",
                "character_session_receipts","character_session_candidates","character_session_ask_trace")})
        metadata['generation'] = dict(completed=True, error=None, wall_ms=1,
            process_qos=dict(pid=123, supported=False, before=None, applied=None, restored=None))
        gate.write_json(fixture/"manifest.json",metadata); gate.write_json(fixture/"oracle.json",oracle)
        (directory/f"generation-{h}.log").write_text("controlled fixture",encoding="utf-8")
        child,parent,_=_raw_sample(identity=index+1); child["oracle"]=oracle
        raw=directory/f"samples/{h}-0"; raw.mkdir(parents=True)
        import shutil
        for actor in actors:
            shutil.copy2(fixture / gate.ask_audit_name(actor), raw / gate.ask_audit_name(actor, owner=True))
        gate.write_json(raw/"result.json",child); gate.write_json(raw/"parent.json",parent)
        owner_ready = {k: v for k, v in child['ready'].items() if k not in {
            'caches', 'parent_pid', 'owner_restore_ms', 'parent_peak_rss_bytes', 'owner_peak_rss_bytes', 'rss_scope'}}
        owner_ready.update(restore_ms=child['ready']['owner_restore_ms'],
                           process_peak_rss_bytes=child['ready']['owner_peak_rss_bytes'])
        gate.write_json(raw/'result.owner-ready.json', owner_ready)
        gate.write_json(raw/'result.owner-result.json', dict(ready=dict(owner_ready, caches=child['ready']['caches']),
            oracle=child['oracle'], verification_ms=child['verification_ms']))
        for name in ('collector-qos.json', 'result.owner-qos.json', 'result.parent-qos.json'):
            gate.write_json(raw / name, dict(pid=123, supported=False, before=None, applied=None, restored=None))
        (raw/"stdout.log").write_text(parent["marker"]+"\n",encoding="utf-8"); (raw/"stderr.log").touch()
        cases[h].append(gate._measurement(child,parent,oracle))
    gate.write_json(directory/"report.json",gate._summary(cases,population=2,tail=8,repeats=1))
    manifest=dict(**identity,schema_version=2,profile="population-long-session-recovery",status="smoke_checked",errors=[],
        configuration=config,samples=samples)
    manifest["raw_artifacts"]={name:gate.file_digest((directory/name).read_bytes()) for name in gate._raw_paths(config["histories"],samples)}
    gate.write_json(directory/"manifest.json",manifest)
    return manifest


@pytest.mark.parametrize("fault",[None,"summary","duplicate","missing","empty_oracle","old_source","failed_generation","missing_generation"])
def test_offline_recovery_rebuilds_cases_without_opening_database(tmp_path,monkeypatch,fault):
    manifest=_evidence(tmp_path,monkeypatch)
    # 数据库不属于证据 allowlist；离线复验不能打开它或计算它的摘要。
    (tmp_path/"graph.sqlite3").write_bytes(b"unrelated mutable database")
    monkeypatch.setattr(gate.sqlite3,"connect",lambda *a,**k:pytest.fail("offline opened database"))
    if fault=="summary": gate.write_json(tmp_path/"report.json",dict(passed=True))
    if fault=="duplicate": manifest["samples"][1]=manifest["samples"][0]
    if fault=="missing": (tmp_path/"samples/16-0/parent.json").unlink()
    if fault=="empty_oracle": gate.write_json(tmp_path/"fixtures/16/oracle.json",{})
    if fault=="old_source": manifest["source"]={}
    if fault in {'failed_generation', 'missing_generation'}:
        path = tmp_path / 'fixtures/16/manifest.json'
        fixture = json.loads(path.read_text(encoding='utf-8'))
        if fault == 'missing_generation':
            fixture.pop('generation')
        else:
            fixture['generation'].update(completed=False, error='OSError')
        gate.write_json(path, fixture)
    if fault in {"summary","empty_oracle","failed_generation","missing_generation"}:
        manifest["raw_artifacts"]={name:gate.file_digest((tmp_path/name).read_bytes()) for name in manifest["raw_artifacts"]}
    gate.write_json(tmp_path/"manifest.json",manifest)
    if fault is None:
        assert gate.verify_artifacts(tmp_path,expected_commit="a"*40,require_formal=False)["diagnostic_passed"]
        with pytest.raises(ValueError,match="formal"): gate.verify_artifacts(tmp_path,expected_commit="a"*40)
    else:
        with pytest.raises((ValueError,KeyError,OSError)): gate.verify_artifacts(tmp_path,expected_commit="a"*40,require_formal=False)


def test_failure_records_this_run_and_replaces_old_latest_summary(tmp_path,monkeypatch):
    gate.write_json(tmp_path/"report.json",dict(passed=True))
    monkeypatch.setattr(gate,"_source_identity",lambda:dict(base_commit="a"*40,source={}))
    monkeypatch.setattr(gate.subprocess,"run",lambda *a,**k:(_ for _ in ()).throw(OSError("controlled generation failure")))
    assert not gate.run_gate(SimpleNamespace(output=tmp_path,population=2,histories=[16,32],tail_windows=8,repeats=1))
    report=json.loads((tmp_path/"report.json").read_text(encoding="utf-8"))
    assert report["passed"] is False
    manifest=json.loads(Path(report["manifest"]).read_text(encoding="utf-8"))
    assert manifest["status"]=="failed" and "controlled generation failure" in manifest["errors"][0]


@pytest.mark.parametrize('table', ['graph_relations', 'character_session_candidates', 'character_session_receipts'])
def test_offline_recovery_requires_every_original_history_table_to_grow(tmp_path, monkeypatch, table):
    _evidence(tmp_path, monkeypatch)
    manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    for history in manifest['configuration']['histories']:
        path = tmp_path / f'fixtures/{history}/manifest.json'
        row = json.loads(path.read_text(encoding='utf-8'))
        row['graph_history_rows'][table] = 0
        gate.write_json(path, row)
    manifest['raw_artifacts'] = {name: gate.file_digest((tmp_path / name).read_bytes()) for name in manifest['raw_artifacts']}
    gate.write_json(tmp_path / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='recovery_history_prefix_did_not_grow'):
        gate.verify_artifacts(tmp_path, expected_commit='a'*40, require_formal=False)


@pytest.mark.parametrize('fault', ['missing_ready', 'missing_result', 'ready_time', 'owner_error', 'oracle', 'counter'])
def test_offline_recovery_binds_original_owner_records(tmp_path, monkeypatch, fault):
    manifest = _evidence(tmp_path, monkeypatch)
    monkeypatch.setattr(gate.sqlite3, 'connect', lambda *a, **k: pytest.fail('offline opened database'))
    raw = tmp_path / 'samples/16-0'
    if fault.startswith('missing'):
        (raw / ('result.owner-ready.json' if fault == 'missing_ready' else 'result.owner-result.json')).unlink()
    else:
        name = 'result.owner-ready.json' if fault == 'ready_time' else 'result.owner-result.json'
        path = raw / name
        row = json.loads(path.read_text(encoding='utf-8'))
        if fault == 'ready_time': row['restore_ms'] = 999999
        if fault == 'owner_error': row = dict(error='CancelledError', owner_pid=1001)
        if fault == 'oracle': row['oracle']['authority_events'] += 1
        if fault == 'counter': row['ready']['calls']['decode:state'] += 1
        gate.write_json(path, row)
    # 重算已有原始摘要不能代替两端原记录的精确关联。
    manifest['raw_artifacts'] = {name: gate.file_digest((tmp_path/name).read_bytes())
        for name in manifest['raw_artifacts'] if (tmp_path/name).is_file()}
    gate.write_json(tmp_path/'manifest.json', manifest)
    with pytest.raises((ValueError, OSError)):
        gate.verify_artifacts(tmp_path, expected_commit='a'*40, require_formal=False)


def test_failed_measurement_preserves_original_owner_records(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, '_source_identity', lambda: dict(base_commit='a'*40, source={}))
    monkeypatch.setattr(gate, '_validate_fixture', lambda *a, **k: None)
    for history in (16, 32):
        fixture = tmp_path/f'fixture-{history}'
        fixture.mkdir()
        for name in ('manifest.json', 'oracle.json', 'roster.json'):
            gate.write_json(fixture/name, {})
        from scripts.verification.population_ask_audit import FORMAT, verify_audit
        actors = {}
        for actor in ('char_a', 'char_b'):
            path = fixture / gate.ask_audit_name(actor)
            path.write_text(json.dumps(dict(format=FORMAT, actor_id=actor)) + '\n' + json.dumps(dict(kind='end')) + '\n', encoding='utf-8')
            actors[actor] = dict(knowledge=verify_audit(path, actor))
        gate.write_json(fixture / 'oracle.json', dict(actors=actors))
    async def failed_measure(directory, output):
        gate.write_json(output.with_suffix('.owner-ready.json'), dict(owner_pid=123, restore_ms=1))
        gate.write_json(output.with_suffix('.owner-result.json'), dict(owner_pid=123, error='CancelledError'))
        raise RuntimeError('controlled owner failure')
    monkeypatch.setattr(gate, 'measure_process', failed_measure)
    assert not gate.run_gate(SimpleNamespace(output=tmp_path, population=2, histories=[16,32], tail_windows=8, repeats=1))
    latest = json.loads((tmp_path/'report.json').read_text(encoding='utf-8'))
    manifest_path = Path(latest['manifest'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name in ('result.owner-ready.json', 'result.owner-result.json'):
        relative = 'samples/16-0/' + name
        assert manifest['raw_artifacts'][relative] == gate.file_digest((manifest_path.parent/relative).read_bytes())
    assert manifest['status'] == 'failed'


@pytest.mark.parametrize('side', ['fixtures/16/ask-char_a.jsonl', 'samples/16-0/result.owner-ask-char_a.jsonl'])
@pytest.mark.parametrize('fault', ['missing', 'changed_source', 'gap'])
def test_offline_recovery_recomputes_each_independent_complete_ask_stream(tmp_path, monkeypatch, side, fault):
    manifest = _evidence(tmp_path, monkeypatch)
    path = tmp_path / side
    if fault == 'missing':
        path.unlink()
    else:
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        index = next(index for index, row in enumerate(rows) if row.get('kind') == 'conflicts')
        if fault == 'gap': rows.pop(index)
        else: rows[index]['value']['source_refs']['suffix'].append('changed-source')
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
    manifest['raw_artifacts'] = {name: gate.file_digest((tmp_path/name).read_bytes()) for name in manifest['raw_artifacts'] if (tmp_path/name).is_file()}
    gate.write_json(tmp_path / 'manifest.json', manifest)
    monkeypatch.setattr(gate.sqlite3, 'connect', lambda *a, **k: pytest.fail('offline opened database'))
    with pytest.raises((OSError, ValueError)):
        gate.verify_artifacts(tmp_path, expected_commit='a'*40, require_formal=False)


def test_failed_generation_preserves_partial_original_ask_audit(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setattr(gate, '_source_identity', lambda: dict(base_commit='a'*40, source={}))
    raw = b'{"format":"ask-complete-audit-v1","actor_id":"char_a"}\n'
    def fail(command, **kwargs):
        fixture = Path(command[command.index('--generate-child') + 1])
        fixture.mkdir()
        (fixture / 'ask-char_a.jsonl').write_bytes(raw)
        raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(gate.subprocess, 'run', fail)
    assert not gate.run_gate(SimpleNamespace(output=tmp_path, population=2, histories=[16,32], tail_windows=8, repeats=1))
    latest = json.loads((tmp_path / 'report.json').read_text(encoding='utf-8'))
    manifest_path = Path(latest['manifest'])
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    relative = 'fixtures/16/ask-char_a.jsonl'
    assert (manifest_path.parent / relative).read_bytes() == raw
    assert manifest['raw_artifacts'][relative] == gate.file_digest(raw)
    assert manifest['status'] == 'failed'

def test_ready_caches_observes_activation_history_and_receipts():
    runtime = SimpleNamespace(
        _memory_store=SimpleNamespace(_light=SimpleNamespace(_events_by_actor={}),
            _graph=SimpleNamespace(_normalizer=SimpleNamespace(_events_by_actor={}))),
        _session_store=SimpleNamespace(_events_by_actor={}), _activation_receipts={'one':object()},
        _activation_authority=SimpleNamespace(_replay_result=SimpleNamespace(
            state={'other-owner':{}}, source_revision_vector={'other-owner':1}, applied_event_ids=['a','b'])))
    main = SimpleNamespace(character_agent_runtime=runtime,
        heavenly_graph=SimpleNamespace(**{key:{} for key in ('_nodes','_relations','_idempotency','_checkpoints','_branch_markers')}),
        gameplay_event_store=SimpleNamespace(_events=[],_transactions={},_outbox={}))
    driver = SimpleNamespace(world_runtime=SimpleNamespace(_confirmed_receipts={},_confirmed_fingerprints={}))
    result = gate.ready_caches(main, driver)
    assert result['activation_receipts'] == 1
    assert result['activation_history'] == dict(state=1, source_revision_vector=1, applied_event_ids=2)
    del runtime._activation_authority._replay_result
    assert gate.ready_caches(main, driver)['activation_history'] == dict(state=0, source_revision_vector=0, applied_event_ids=0)


def test_cold_ready_rejects_hidden_activation_history():
    for field in ('state', 'source_revision_vector', 'applied_event_ids'):
        child, parent, expected = _raw_sample()
        child['ready']['caches']['activation_history'][field] = 1
        with pytest.raises(ValueError, match='history_cache'):
            gate._measurement(child, parent, expected)
