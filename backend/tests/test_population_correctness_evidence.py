"""离线正确性复验的合成合同测试，不作为运行时验收证据。"""
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from scripts.verification import verify_population_runtime_correctness as gate


def _evidence(directory, monkeypatch):
    source = {"source_sha256": "controlled", "files": {}}
    monkeypatch.setattr(gate, "source_snapshot", lambda _: source)
    revision, stamp = "a" * 40, "2026-09-17T00:00:00+00:00"
    (directory / "legacy").mkdir()
    steps = []
    registry = gate.load_profile_registry(gate.ROOT).profiles
    for name, filename in gate.PROFILES:
        (directory / f"{name}.log").write_text("controlled subprocess output", encoding="utf-8")
        steps.append(dict(profile=name, status="passed", exit_code=0, timeout_seconds=gate.TIMEOUT_SECONDS,
            report=f"legacy/{filename}", command=["python", str(gate.ROOT / registry[name]["script"])], started_at=stamp, finished_at=stamp))
    persistence = dict(test_returncode=0, overall_passed=True, git_head=revision, optimized_probe=dict(
        delete_from_graph_tables=0, graph_nodes_inserts=1, restored_graph_nodes=2), scale_probes=[], session_checkpoint_probes=[])
    for n in (100, 1000, 10000):
        persistence["scale_probes"].append(dict(population=n, samples=30, passed=True, delete_count=0,
            whole_graph_snapshot_calls=0, undo_entries=[1]*30, sql_changed_rows=[5]*30, reopened_node_versions=n+30,
            sql_write_tables={table:30 for table in ("graph_nodes", "graph_stream_revisions", "graph_idempotency", "graph_revision_summaries", "graph_current_times")}))
        persistence["session_checkpoint_probes"].append(dict(population=n, samples=30, passed=True,
            checkpoint_event_indexes=[], checkpoint_count=0, current_state_contains_history=[False]*30,
            runtime_reopened_revision=30, session_reopened_event_count=n+31,
            runtime_reopened_event_count=n+61, runtime_event_count_before_reopen=n+61,
            sqlite_page_size=8192, continuity_receipt_statuses=['committed']*30,
            session_append_bytes=[8192]*30, session_serialized_event_bytes=[500]*30,
            current_state_serialized_bytes=[300]*30,
            current_state_event_indexes=list(range(n+32,n+62))))
    incremental = dict(overall_passed=True, git_head=revision, test_returncode=0, history_scenarios=[], projection_scale_scenarios=[])
    for h in (1000,10000,50000):
        incremental["history_scenarios"].append(dict(history=h,population=100,tail=10,prefix_checkpoint_sequence=h,
            output_hash="same",full_oracle_hash="same",sample_count=5,samples=[dict(published=True,
                read_events_calls=1,read_events_returned=10,read_stream_calls=1,read_stream_returned=1) for _ in range(5)]))
    for n in (54,100,1000,10000):
        incremental["projection_scale_scenarios"].append(dict(population=n,sample_count=5,
            samples=[dict(published=True) for _ in range(5)],input_hash="same",output_hash="same",
            published_projection_count=n,pipeline_audit_count=5))
    continuous_xml=ET.Element("testsuite")
    props=ET.SubElement(ET.SubElement(continuous_xml,"testcase",name="controlled"),"properties")
    ET.SubElement(props,"property",name="continuous_runtime_evidence",value=json.dumps(dict(window_count=2,actor_ids=["char_a"])))
    for n in (2,17):
        actors=[f"actor_{i}" for i in range(n)]
        ET.SubElement(props,"property",name=f"configured_roster_{n}",value=json.dumps(dict(
            actor_ids=actors,b0_actor_ids=actors,default_fill=False,character_core_actor_ids=[])))
    ET.ElementTree(continuous_xml).write(directory/"legacy/population-continuous-runtime-tests.xml",encoding="utf-8")
    continuous=dict(overall_passed=True,test_count=1,exit_code=0)
    hot=dict(overall_passed=True,git_head=revision,scenarios=[])
    for n in (54,100,1000,10000):
        row=dict(population=n,owner_receipt_input_count=0,capability_due_count=0,replay_final_hot_hash="same")
        for field in ("projection_hash","read_set_digest","capability_hash","candidate_hash","deferred_hash","owner_receipt_input_hash","final_hot_hash"):
            row.update({f"{prefix}_{field}":"same" for prefix in ("baseline","serial","parallel")})
        row.update({name:dict(result_digest="same") for name in ("confirmation","parallel_confirmation","replay_confirmation")})
        hot["scenarios"].append(row)
    for (_,filename),report in zip(gate.PROFILES,(persistence,incremental,continuous,hot)):
        (directory/"legacy"/filename).write_text(json.dumps(report),encoding="utf-8")
    focused=ET.Element("testsuite")
    for name in gate.FOCUSED_TESTS:
        ET.SubElement(focused,"testcase",classname=f"tests.{Path(name).stem}",name="controlled")
    ET.ElementTree(focused).write(directory/"focused.xml",encoding="utf-8")
    (directory/"focused.log").write_text("controlled focused output",encoding="utf-8")
    tmp_output = directory / "focused.xml"
    steps.append(dict(profile="runtime-focused-tests",status="passed",exit_code=0,pytest_workers=1,
        timeout_seconds=gate.TIMEOUT_SECONDS,junit="focused.xml",test_count=len(gate.FOCUSED_TESTS),
        command=["python","-m","pytest","-q","-o","junit_family=legacy",f"--junitxml={tmp_output}",
                 *(str(gate.ROOT / "backend/tests" / name) for name in gate.FOCUSED_TESTS),
                 "--basetemp", str(gate.ROOT / ".harness/pc-evidence")],started_at=stamp,finished_at=stamp))
    manifest=dict(schema_version=1,profile=gate.NAME,base_commit=revision,source=source,status="passed",
        overall_passed=True,errors=[],steps=steps,started_at=stamp,finished_at=stamp)
    return manifest


@pytest.mark.parametrize("fault",[None,"digest","old","missing_tests","skipped","five_tables","hot_oracle","history_reads","roster"])
def test_correctness_offline_recomputes_raw_contracts(tmp_path,monkeypatch,fault):
    manifest=_evidence(tmp_path,monkeypatch)
    if fault=="old": manifest["base_commit"]="b"*40
    if fault in {"missing_tests","skipped"}:
        path=tmp_path/"focused.xml"
        tree=ET.parse(path)
        if fault=="missing_tests":
            tree.getroot().remove(tree.getroot()[0])
            manifest["steps"][-1]["test_count"]-=1
        else: ET.SubElement(tree.getroot()[0],"skipped")
        tree.write(path,encoding="utf-8")
    index={"five_tables":0,"history_reads":1,"hot_oracle":3}.get(fault)
    if index is not None:
        path=tmp_path/"legacy"/gate.PROFILES[index][1]
        report=json.loads(path.read_text(encoding="utf-8"))
        if fault=="five_tables": report["scale_probes"][0]["sql_changed_rows"][0]=6
        if fault=="history_reads": report["history_scenarios"][0]["samples"][0]["read_events_returned"]=1000
        if fault=="hot_oracle": report["scenarios"][0]["parallel_projection_hash"]="different"
        path.write_text(json.dumps(report),encoding="utf-8")
    if fault=="roster":
        path=tmp_path/"legacy/population-continuous-runtime-tests.xml"
        tree=ET.parse(path)
        prop=tree.find(".//property[@name='configured_roster_17']")
        row=json.loads(prop.get("value")); row["default_fill"]=True
        prop.set("value",json.dumps(row)); tree.write(path,encoding="utf-8")
    manifest["raw_artifacts"]={path.relative_to(tmp_path).as_posix():dict(sha256=gate.digest(path.read_bytes()),bytes=path.stat().st_size)
        for path in tmp_path.rglob("*") if path.is_file()}
    (tmp_path/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    if fault=="digest": (tmp_path/"focused.log").write_text("tampered",encoding="utf-8")
    if fault is None:
        assert gate.verify_artifacts(tmp_path,expected_commit="a"*40)["passed"]
    else:
        with pytest.raises(ValueError): gate.verify_artifacts(tmp_path,expected_commit="a"*40)


@pytest.mark.parametrize('fault', ['wal_zero','wal_huge','serialized_spread','missing_current','counts','uncommitted','missing_page','test_exit','fake_page'])
def test_session_raw_contract_tampering_is_rejected(tmp_path, monkeypatch, fault):
    manifest = _evidence(tmp_path, monkeypatch)
    path = tmp_path / 'legacy' / gate.PROFILES[0][1]
    report = json.loads(path.read_text())
    row = report['session_checkpoint_probes'][0]
    if fault == 'wal_zero': row['session_append_bytes'] = [0]*30
    if fault == 'wal_huge': row['session_append_bytes'] = [2**30]*30
    if fault == 'serialized_spread': row['session_serialized_event_bytes'] = [100, 100000]*15
    if fault == 'missing_current': row['current_state_serialized_bytes'] = []
    if fault == 'counts':
        row.update(session_reopened_event_count=0, runtime_reopened_event_count=30, runtime_event_count_before_reopen=30,
                   current_state_event_indexes=list(range(1,31)))
    if fault == 'uncommitted': row['continuity_receipt_statuses'][0] = 'replayed'
    if fault == 'missing_page': del row['sqlite_page_size']
    if fault == 'test_exit': report['test_returncode'] = 1
    if fault == 'fake_page':
        row['sqlite_page_size'] = 2**30
        row['session_append_bytes'] = [2**30]*30
    path.write_text(json.dumps(report), encoding='utf-8')
    manifest['raw_artifacts'] = {path.relative_to(tmp_path).as_posix():dict(sha256=gate.digest(path.read_bytes()),bytes=path.stat().st_size)
        for path in tmp_path.rglob('*') if path.is_file()}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError): gate.verify_artifacts(tmp_path, expected_commit='a'*40)


@pytest.mark.parametrize('extra', [['--deselect=x'], ['-k','one'], ['-n','8'], ['external'], ['mixed_roots']])
def test_focused_command_is_exact(tmp_path, monkeypatch, extra):
    manifest = _evidence(tmp_path, monkeypatch)
    command = manifest['steps'][-1]['command']
    if extra == ['external']: command[7] = '/other/tests/' + gate.FOCUSED_TESTS[0]
    elif extra == ['mixed_roots']: command[7:-2] = ['Z:/unrelated/backend/tests/' + name for name in gate.FOCUSED_TESTS]
    else: command.extend(extra)
    manifest['raw_artifacts'] = {path.relative_to(tmp_path).as_posix():dict(sha256=gate.digest(path.read_bytes()),bytes=path.stat().st_size)
        for path in tmp_path.rglob('*') if path.is_file()}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError): gate.verify_artifacts(tmp_path, expected_commit='a'*40)


def test_focused_command_allows_original_machine_root_after_evidence_move(tmp_path, monkeypatch):
    manifest = _evidence(tmp_path, monkeypatch)
    command = manifest['steps'][-1]['command']
    registry = gate.load_profile_registry(gate.ROOT).profiles
    for step in manifest['steps'][:-1]:
        step['command'][1] = 'Z:/capture-machine/' + registry[step['profile']]['script']
    command[6] = '--junitxml=Q:/independent-output/run/focused.xml'
    command[7:-2] = ['Z:/capture-machine/backend/tests/' + name for name in gate.FOCUSED_TESTS]
    command[-1] = 'Z:/capture-machine/.harness/pc-old'
    manifest['raw_artifacts'] = {path.relative_to(tmp_path).as_posix():dict(sha256=gate.digest(path.read_bytes()),bytes=path.stat().st_size)
        for path in tmp_path.rglob('*') if path.is_file()}
    (tmp_path/'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    assert gate.verify_artifacts(tmp_path, expected_commit='a'*40)['passed']
