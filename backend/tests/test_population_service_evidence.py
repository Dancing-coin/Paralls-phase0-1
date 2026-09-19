"""隔离门禁的离线证据检查；合成样本仅验证拒绝规则，不是真实负载结果。"""
from copy import deepcopy
import json
import sys

import pytest

from scripts.verification import verify_population_service_isolation as probe
from test_population_service_isolation_gate import valid_measurements


@pytest.mark.parametrize(("arguments", "expected"), [
    ([], [100, 1000]),
    (["--population", "10000"], [10000]),
])
def test_service_cli_defaults_to_current_matrix_but_accepts_explicit_10000(tmp_path, monkeypatch, arguments, expected):
    collected = []
    monkeypatch.setattr(sys, "argv", ["service", "--output", str(tmp_path / "capture"), *arguments])
    monkeypatch.setattr(probe, "collect", lambda directory, population, seconds: collected.append(population) or {"passed": True})
    monkeypatch.setattr(probe, "write_json", lambda *_: None)

    assert probe.main() == 0
    assert collected == expected


def process_records(server):
    """合成证据的两个真实角色；不运行服务，不作为性能样本。"""
    owner = deepcopy(server)
    parent = {key: owner.pop(key) for key in ('parent_pid', 'child_exit_code', 'heartbeat_ms',
        'heartbeat_expected_at', 'queue_peak', 'execution_credit', 'asgi_lifecycle',
        'parent_drained', 'parent_drained_at')}
    for key in ('writer_calls', 'mutation_threads', 'writer_boundaries'):
        parent[key] = owner.pop('parent_' + key)
    parent.update(child_pid=owner['owner_pid'], errors=[],
        **{key: owner[key] for key in ('load_started_at', 'load_ended_at', 'population', 'window_size')})
    ready = {key: owner[key] for key in ('owner_pid', 'population', 'window_size')}
    return parent, owner, ready


def test_process_observations_require_matching_real_roles_and_intervals():
    _, server = valid_measurements()
    server.update(population=100, window_size=1)
    parent, owner, ready = process_records(server)
    assert probe.merge_process_observations(parent, owner, ready) == server
    for role, field, value in [('parent', 'child_pid', 102), ('ready', 'owner_pid', 102),
            ('parent', 'population', 1000), ('ready', 'window_size', 86400),
            ('owner', 'load_ended_at', 123.), ('parent', 'load_started_at', 1.)]:
        changed = deepcopy({'parent': parent, 'owner': owner, 'ready': ready})
        changed[role][field] = value
        with pytest.raises(ValueError, match='process_observations'):
            probe.merge_process_observations(changed['parent'], changed['owner'], changed['ready'])
    parent['errors'].append('parent_send_failed')
    assert probe.merge_process_observations(parent, owner, ready)['errors'] == ['parent_send_failed']


def test_offline_service_gate_recomputes_samples_and_checks_source_population_and_raw(tmp_path, monkeypatch):
    client, server = valid_measurements()
    server.update(heartbeat_expected_at=[i * .01 for i in range(1, 12000)], heartbeat_ms=[1.] * 11999,
        window_started_at=[float(i) for i in range(1, 120)], window_ms=[100.] * 119)
    server.update(population=100, window_size=1, provider_mode="controlled_local_one_second_delay")
    source = {"source_sha256": "fixed-test-source", "files": {}}
    monkeypatch.setattr(probe, "source_manifest", lambda: source)
    files = {"client.json": client, "server.json": server,
             "roster.json": {"actor_ids": ["char_a", "char_b", "char_c", *[f"resident_{i:05d}" for i in range(97)]]},
             "start": {key: client[key] for key in ("load_started_at", "load_ended_at")}}
    manifest = dict(schema_version=1, profile="population-service-isolation", base_commit="abc123",
        source=source, population=100, seconds=120, errors=[], backend_exit_code=0,
        provider_mode="controlled_local_slow_not_live_proof", godot_status="godot_unverified", **probe.evaluate(client, server))
    records = [{"channel": "health", "key": i, "expected_at": i / 20,
                "completed_at": i / 20 + .01, "status": "ok"} for i in range(2400)]
    for kind, rate in (("read", 5), ("fact", 2), ("dialogue", .1)):
        records.extend(dict(channel=kind, ordinal=i, type="sent", expected_at=i / rate,
                            sent_at=i / rate, producer_ts=1000 + i) for i in range(client["offered"][kind]))
        for i in range(client["offered"][kind]):
            key = 1000 + i if kind == "fact" else i
            if kind in ("read", "fact"):
                records.append(dict(channel=kind, type="runtime_admission", key=key, request_id=f"service-{kind}:{i}", received_at=i / rate + .01, accepted=True))
                records.append(dict(channel=kind, type="runtime_completion", key=key, request_id=f"service-{kind}:{i}", received_at=i / rate + .02, status="owner_finished"))
                records.append(dict(channel=kind, type="ack", key=key, request_id=f"service-{kind}:{i}", received_at=i / rate + .02, accepted=True))
            if kind == "fact":
                records.append(dict(channel=kind, type="spatial_access_runtime_state_snapshot", key=key, request_id=f"service-{kind}:{i}",
                                    received_at=i / rate + .02))
            if kind == "dialogue":
                records.append(dict(channel=kind, type="dialogue_stream_end", key=f"service-dialogue:{i}",
                                    received_at=i / rate + 1, status="completed"))
    (tmp_path / "responses.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records), encoding="utf-8")
    (tmp_path / "process.log").write_text("", encoding="utf-8")
    (tmp_path / "stop").touch()

    def save(values, metadata):
        for name, value in values.items():
            (tmp_path / name).write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
        for name, value in zip(('parent-observed.json', 'owner-observed.json', 'owner-ready.json'),
                               process_records(values['server.json'])):
            (tmp_path / name).write_text(json.dumps(value, allow_nan=False), encoding='utf-8')
        metadata["raw_artifacts"] = probe.raw_artifacts(tmp_path)
        (tmp_path / "manifest.json").write_text(json.dumps(metadata), encoding="utf-8")

    save(files, manifest)
    assert probe.verify_artifacts(tmp_path, expected_commit="abc123")["passed"]
    # 两个原始角色与派生摘要一起篡改并重算 hash，仍不能缩小真实探针边界或隐藏停机失败。
    for replacement in (['gameplay_durable_append'], ['unknown_writer'],
                        [*server['writer_boundaries'], server['writer_boundaries'][0]], None):
        altered, metadata = deepcopy(files), deepcopy(manifest)
        if replacement is None:
            altered['server.json']['asgi_lifecycle']['shutdown_failed'] = True
        else:
            altered['server.json']['writer_boundaries'] = replacement
            altered['server.json']['parent_writer_boundaries'] = replacement
        save(altered, metadata)
        with pytest.raises(ValueError, match='measurements_failed'):
            probe.verify_artifacts(tmp_path, expected_commit='abc123')
    save(files, manifest)
    # 即使同步重算文件摘要，也不能用拼接 server 摘要替代两个角色的实际原始记录。
    for name, key, value in [('owner-observed.json', 'owner_pid', 102),
            ('owner-observed.json', 'writer_calls', {}), ('parent-observed.json', 'heartbeat_ms', []),
            ('parent-observed.json', 'writer_calls', {'gameplay_durable_append': 1}),
            ('owner-ready.json', 'population', 1000)]:
        save(files, manifest)
        raw = json.loads((tmp_path / name).read_text(encoding='utf-8'))
        raw[key] = value
        (tmp_path / name).write_text(json.dumps(raw), encoding='utf-8')
        manifest['raw_artifacts'] = probe.raw_artifacts(tmp_path)
        (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        with pytest.raises(ValueError, match='process_observations'):
            probe.verify_artifacts(tmp_path, expected_commit='abc123')
    save(files, manifest)
    # 真实起点可抖动/追赶，末窗晚完成仍计全部耗时；排空样本不能稀释负载期。
    altered, metadata = deepcopy(files), deepcopy(manifest)
    observed = altered["server.json"]
    observed["window_started_at"] = [value + .3 for value in observed["window_started_at"]]
    observed["window_started_at"][20] += .4
    observed["window_ms"][-1] = 2000.
    observed["window_started_at"].append(122.)
    observed["window_ms"].append(1.)
    metadata.update(probe.evaluate(altered["client.json"], observed))
    save(altered, metadata)
    assert probe.verify_artifacts(tmp_path, expected_commit="abc123")["passed"]
    save(files, manifest)
    for kind in ("heartbeat_compressed", "heartbeat_gap", "window_compressed", "window_tail_missing"):
        altered, metadata = deepcopy(files), deepcopy(manifest)
        observed = altered["server.json"]
        if kind == "heartbeat_compressed":
            observed["heartbeat_expected_at"] = [i / 1000000 for i in range(11999)]
        elif kind == "heartbeat_gap":
            observed["heartbeat_expected_at"][6000] += .001
        elif kind == "window_compressed":
            observed["window_started_at"] = [i / 1000000 for i in range(119)]
        else:
            observed["window_started_at"][-1] = 118.5
        metadata.update(probe.evaluate(altered["client.json"], observed))
        save(altered, metadata)
        with pytest.raises(ValueError, match="coverage"):
            probe.verify_artifacts(tmp_path, expected_commit="abc123")
    save(files, manifest)
    with pytest.raises(ValueError, match="identity"):
        probe.verify_artifacts(tmp_path, expected_commit="old")

    for target, key, value in (
        ("manifest", "population", 10000), ("manifest", "seconds", 121),
        ("manifest", "backend_exit_code", 1), ("manifest", "passed", False),
        ("manifest", "metrics", {}), ("server.json", "population", 10000),
        ("server.json", "heartbeat_ms", [-1.] * 12000),
        ("server.json", "window_ms", [801.] * 120),
        ("server.json", "window_size", 86400),
        ("client.json", "accepted_ms", [10.]),
        ("client.json", "seconds", 3),
    ):
        altered, metadata = deepcopy(files), deepcopy(manifest)
        (metadata if target == "manifest" else altered[target])[key] = value
        save(altered, metadata)
        with pytest.raises(ValueError):
            probe.verify_artifacts(tmp_path, expected_commit="abc123")
    save(files, manifest)
    # 重算摘要仍不能隐藏重复、拒绝或缺少原始应答。
    for changed in (records[:-1], [*records, records[-1]],
                    [dict(row, accepted=False) if row.get("type") == "ack" else row for row in records]):
        (tmp_path / "responses.jsonl").write_text("".join(json.dumps(row) + "\n" for row in changed), encoding="utf-8")
        save(files, manifest)
        with pytest.raises(ValueError):
            probe.verify_artifacts(tmp_path, expected_commit="abc123")
    (tmp_path / "responses.jsonl").write_text("", encoding="utf-8")
    save(files, manifest)  # 即使同步改摘要，也不能用缺失原始流量记录通过。
    with pytest.raises(ValueError):
        probe.verify_artifacts(tmp_path, expected_commit="abc123")
    (tmp_path / "process.log").unlink()
    save(files, manifest)
    with pytest.raises(ValueError):
        probe.verify_artifacts(tmp_path, expected_commit="abc123")


def test_online_collection_cannot_accept_aggregate_counts_without_original_responses(tmp_path, monkeypatch):
    client,server=valid_measurements()
    server.update(population=100, window_size=1)
    target=tmp_path/'capture'
    monkeypatch.setattr(probe,'source_manifest',lambda: {'source_sha256':'control','files':{}})
    monkeypatch.setattr(probe.subprocess,'check_output',lambda *args,**kwargs:'control')
    class Child:
        returncode=0
        def __init__(self,*args,**kwargs):
            (target/'ready.json').write_text('{}')
            (target/'server.json').write_text(json.dumps(server))
            for name, value in zip(('parent-observed.json', 'owner-observed.json', 'owner-ready.json'),
                                   process_records(server)):
                (target/name).write_text(json.dumps(value))
        def poll(self):return 0
        def wait(self,**kwargs):return 0
    monkeypatch.setattr(probe.subprocess,'Popen',Child)
    async def load(directory,seconds):
        (directory/'client.json').write_text(json.dumps(client))
        (directory/'responses.jsonl').write_text('')
        return client
    monkeypatch.setattr(probe,'load',load)
    report=probe.collect(target,100,120)
    assert report['backend_exit_code']==0
    assert not report['passed'] and report['errors']==['ValueError']
    assert (target/'manifest.json').is_file()
