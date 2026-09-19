import json
from copy import deepcopy

import pytest

from scripts.verification.verify_population_transport_cost import WireEvidence, compare_runs
from app.gameplay.godot_mirror_delivery import GameplayMirrorDeltaEncoder
from test_mirror_delta_transport import _message, _send


@pytest.mark.parametrize('raw,error', [('{"owner_pid":17}', None), ('{"owner_pid":NaN}', ValueError)])
def test_cost_owner_marker_retries_short_lock_and_preserves_strict_json(tmp_path, monkeypatch, raw, error):
    import asyncio
    from pathlib import Path
    from types import SimpleNamespace
    from scripts.verification import verify_population_transport_cost as cost

    path = tmp_path / 'owner-ready.json'
    path.write_text(raw, encoding='utf-8')
    original = Path.read_text
    calls = []
    def locked_read(target, *args, **kwargs):
        if target == path:
            calls.append(target)
            if len(calls) == 1:
                raise PermissionError('transient sharing lock')
        return original(target, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', locked_read)
    owner = SimpleNamespace(is_alive=lambda: True)
    if error is None:
        assert asyncio.run(cost._owner_file(tmp_path, path.name, owner)) == dict(owner_pid=17)
    else:
        with pytest.raises(error, match='nonfinite_json'):
            asyncio.run(cost._owner_file(tmp_path, path.name, owner))
    assert len(calls) == 2


def test_cost_wire_evidence_counts_real_utf8_and_checks_exact_delta():
    evidence = WireEvidence({"actor:a"})
    encoder = GameplayMirrorDeltaEncoder()
    first = _send(encoder, _message(1))
    second = _send(encoder, _message(2, revision=2))
    for message in (first, second):
        evidence.receive(json.dumps(message, ensure_ascii=False))
    assert evidence.bytes_received == sum(len(json.dumps(message, ensure_ascii=False).encode()) for message in (first, second))
    assert evidence.counts == {"snapshot": 1, "delta": 1}
    assert evidence.sequence == 2
    assert evidence.snapshots["actor:a"].facade_revision == second["payload"]["facade_revision"]
    for change in ("base", "scope", "gap", "groups"):
        broken = deepcopy(second)
        if change == "base":
            broken["payload"]["payload"]["base_snapshot_checksum"] = "sha256:" + "0" * 64
        elif change == "scope":
            broken["payload"]["actor_ref"] = "actor:private"
        elif change == "gap":
            broken["payload"]["delivery_sequence"] = 3
        else:
            broken["payload"]["payload"]["groups"] = {}
        fresh = WireEvidence({"actor:a"})
        fresh.receive(json.dumps(first))
        with pytest.raises(ValueError):
            fresh.receive(json.dumps(broken))


def test_transport_comparison_requires_identical_oracles_and_measured_improvement():
    def row(cost, calls):
        return {"oracle": {"authority": "same", "public": "same"}, "seed_files": {"db": "same"},
                "errors": [], "window_ms": [cost], "delivery_complete_ms": [cost], "checkpoint_validations": [calls],
                "network": {"ws_frame_bytes": 100}, "population": 10000, "windows": 30}
    before, after = [row(10, 161) for _ in range(5)], [row(8, 1) for _ in range(5)]
    result = compare_runs(before, after)
    assert result["equivalent"] and result["improvement_passed"]
    after[0]["oracle"]["authority"] = "changed"
    assert not compare_runs(before, after)["equivalent"]
    assert not compare_runs(before[:1], before[:1])["formal_repeats"]
    assert not compare_runs(before, before)["improvement_passed"]
    assert not compare_runs(before, [row(10, 1) for _ in range(5)])["improvement_passed"]


def test_sqlite_sizes_include_database_named_json_and_its_sidecars(tmp_path):
    import sqlite3
    from scripts.verification.verify_population_transport_cost import _sqlite_files
    path = tmp_path / 'graph.sqlite3.gameplay.json'
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA journal_mode=WAL')
    connection.execute('CREATE TABLE facts(value)')
    connection.commit()
    (tmp_path / 'unrelated.json').write_text('{}')
    sizes = _sqlite_files(tmp_path)
    assert sizes[path.name] == path.stat().st_size
    assert sizes[path.name + '-wal'] > 0
    assert 'unrelated.json' not in sizes
    connection.close()


def test_public_oracle_retains_intermediate_windows():
    from scripts.verification.verify_population_transport_cost import GameplayGodotMirrorSyncAdapter
    from dataclasses import replace
    def packet(seq, tick, value):
        sync = GameplayGodotMirrorSyncAdapter()
        message = _message(seq, revision=tick + 1)
        # 使用真实population公共组载荷和规范重算，错误包本身仍合法。
        view = __import__('test_gameplay_mirror_session_access_service')._projection_source('actor:a')
        group = replace(view.groups['resources'], group_id='population_public', payload={'confirmed_tick': tick, 'position': value})
        snapshot = sync.snapshot(replace(view, groups={'population_public': group}))
        message['payload'].update(facade_revision=snapshot.facade_revision, source_revision_vector=dict(snapshot.source_revision_vector), payload=sync.snapshot_payload(snapshot))
        return message
    before, after = WireEvidence({'actor:a'}), WireEvidence({'actor:a'})
    for sequence, tick in enumerate(range(3), 1):
        before.receive(json.dumps(packet(sequence, tick, tick)))
        after.receive(json.dumps(packet(sequence, tick, 999 if tick == 1 else tick)))
    assert before.snapshots == after.snapshots
    assert before.public_oracle(windows=2) != after.public_oracle(windows=2)
    with pytest.raises(ValueError, match='windows_missing'):
        before.public_oracle(windows=3)
    with pytest.raises(ValueError, match='window_conflict'):
        before.receive(json.dumps(packet(4, 1, 999)))


def test_failed_cost_collect_retains_initial_identity_and_raw(tmp_path, monkeypatch):
    from scripts.verification import verify_population_transport_cost as cost
    monkeypatch.setattr(cost, 'source_manifest', lambda: {'source_sha256': 'original'})
    monkeypatch.setattr(cost.subprocess, 'check_output', lambda *a, **k: 'abc123')
    def fail(*args, **kwargs):
        kwargs['stdout'].write('failed child raw')
        raise RuntimeError('child failure')
    monkeypatch.setattr(cost.subprocess, 'run', fail)
    with pytest.raises(RuntimeError, match='child failure'):
        cost.collect(tmp_path / 'capture', population=100, windows=1, repeats=1)
    report = json.loads((tmp_path / 'capture/manifest.json').read_text())
    assert report['status'] == 'failed'
    assert report['base_commit'] == 'abc123'
    assert report['source']['source_sha256'] == 'original'
    assert report['started_at'] <= report['finished_at']
    assert 'seed-state/process.log' in report['raw_artifacts']


def test_sqlite_sizes_while_runtime_archive_lease_is_held(tmp_path):
    import sqlite3
    from app.world_runtime.storage_lease import RuntimeStorageLease
    from scripts.verification.verify_population_transport_cost import _sqlite_files
    path = tmp_path / 'graph.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('CREATE TABLE facts(value)')
    with RuntimeStorageLease(path):
        assert _sqlite_files(tmp_path) == {path.name: path.stat().st_size}


def test_cost_owner_probe_records_actual_spawn_windows_and_full_authority(tmp_path, monkeypatch):
    import asyncio
    import os
    from scripts.verification import verify_population_transport_cost as cost
    from app import config
    from app.services import runtime_process

    roster = tmp_path / "roster.json"
    cost.write_json(roster, {"actor_ids": ["char_a", "char_b", "resident_test"]})
    cost.write_json(tmp_path / "probe-config.json", {"variant": "after", "windows": 1})
    monkeypatch.setenv("PARALLS_COST_PROBE_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", cost.cost_owner_child)
    settings = config.Settings(heavenly_graph_path=str(tmp_path / "state" / "graph.sqlite3"),
        population_roster_path=str(roster), population_runtime_profile="benchmark_1x",
        character_model_provider_kind="local", siming_llm_mode="disabled")

    async def scenario():
        host = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await host.start()
            ready = await cost._owner_file(tmp_path, "owner-ready.json", host.process)
            assert ready == dict(owner_pid=host.process.pid, population=3, variant="after",
                windows=1, initial_tick=0, clock_profile="manual_window_cost")
            assert host.process.pid != os.getpid()
            assert not (tmp_path / "owner-result.json").exists()
            (tmp_path / "start").touch()
            await asyncio.sleep(.3)
            assert not (tmp_path / "owner-result.json").exists()
            cost.write_json(cost._delivery_ack_path(tmp_path, 1), dict(tick=1, received_at=cost.perf_counter(), actor_count=3))
            (tmp_path / "finish").touch()
            result = await cost._owner_file(tmp_path, "owner-result.json", host.process)
            assert result["owner_pid"] == ready["owner_pid"] and result["errors"] == []
            assert result["authority"]["confirmed_tick"] == 1
            assert result["authority"]["advanced_count"] == 3
            assert len(result["window_started"]) == len(result["window_ms"]) == 1
            assert result["window_ms"][0] > 0 and result["checkpoint_validations"][0] > 0
            assert result["sqlite_file_bytes_before"] and result["sqlite_file_bytes_after"]
            assert result["internal_segment"]["scope"] == "internal"
        finally:
            await host.close()
        assert host.process.exitcode == 0

    asyncio.run(scenario())


def test_cost_offline_verifier_replays_wire_and_rejects_edited_summary(tmp_path, monkeypatch):
    from dataclasses import asdict, replace
    from scripts.verification import verify_population_transport_cost as cost
    from test_gameplay_mirror_session_access_service import _projection_source
    from test_siming_population_authorized_cadence_publication import _cadence

    source = {"source_sha256": "current"}
    monkeypatch.setattr(cost, "source_manifest", lambda: source)
    actors = [f"actor_{i}" for i in range(100)]
    cost.write_json(tmp_path / "roster.json", {"actor_ids": actors})
    rows = {}
    sync = cost.GameplayGodotMirrorSyncAdapter()
    for variant in ("before", "after", "full"):
        folder = tmp_path / (variant if variant == "full" else variant + "-0")
        folder.mkdir()
        encoder = GameplayMirrorDeltaEncoder()
        evidence = WireEvidence({f"character:{actor}" for actor in actors})
        trace = []
        for tick in (0, 1):
            for actor in actors:
                ref = f"character:{actor}"
                view = _projection_source(ref)
                group = replace(view.groups["resources"], group_id="population_public",
                    projection_revision=f"population:{tick}", payload={"confirmed_tick": tick})
                snapshot = sync.snapshot(replace(view, source_facade_revision=f"facade:{tick}", groups={"population_public": group}))
                message = _message(len(trace) + 1, actor=ref)
                message["payload"].update(facade_revision=snapshot.facade_revision,
                    source_revision_vector=dict(snapshot.source_revision_vector), payload=sync.snapshot_payload(snapshot))
                raw = json.dumps(_send(encoder, message, force_snapshot=variant == "full"))
                evidence.receive(raw)
                trace.append({"raw_text": raw, "packet_bytes": len(raw.encode())})
        (folder / "public-messages.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace), encoding="utf-8")
        (folder / "process.log").write_text("owned child exited 0", encoding="utf-8")
        row = dict(variant=variant, population=100, windows=1, seed_files={"db": "same"},
            oracle={"authority": {"confirmed_tick": 1, "population": 100, "advanced_count": 100, "authority_head": 1,
                **{key: ("a" * 64 if key == "gameplay_replay_digest" else cost.object_digest({"field": key})) for key in ("receipt_digest", "checkpoint_digest", "character_revision_digest",
                    "population_state_digest", "gameplay_events_digest", "gameplay_replay_digest",
                    "hot_revision_digest", "stream_revision_digest", "owner_receipt_digest")}},
                "public": evidence.public_oracle(windows=1)},
            window_ms=[10 if variant == "before" else 8], delivery_complete_ms=[10 if variant == "before" else 8],
            checkpoint_validations=[161 if variant == "before" else 1], checkpoint_validate_ms=[1.], sqlite_calls_ms=[1.],
            sqlite_file_bytes_before={"db": 4096}, sqlite_file_bytes_after={"db": 8192}, sqlite_file_size_delta={"db":4096},
            process_peak_rss_bytes=100, reconstruction_segments=[
                asdict(cost.measure_population_transport(_cadence, scope="internal", audience="backend")),
                asdict(cost.measure_population_transport(lambda:cost.GameplayMirrorDeliveryEnvelope.model_validate(message["payload"]), scope="public", audience="godot"))], errors=[],
            network=dict(compression="disabled", handshake_bytes=20, ws_frame_bytes=evidence.bytes_received + 10,
                handshake_bytes_by_direction={"client_to_backend":10,"backend_to_client":10},
                ws_frame_bytes_by_direction={"client_to_backend":10,"backend_to_client":evidence.bytes_received},
                tcp_ip_header_bytes_measured=False, application_payload_bytes=evidence.bytes_received+5,
                application_bytes_by_direction={"client_to_backend":5,"backend_to_client":evidence.bytes_received},
                server_bytes_by_kind=dict(evidence.bytes_by_kind), delivery_counts=dict(evidence.counts),
                client_send_count=1, resync_count=0, loop_queue_peak_encoded_payload_bytes=0, loop_queue_peak_items=0))
        owner = dict(owner_pid=200, variant=variant, population=100, windows=1, errors=[],
            window_started=[1.], authority=row["oracle"]["authority"], peak_rss_bytes=60,
            internal_segment=row["reconstruction_segments"][0], queue_peak_bytes=0, queue_peak_count=0,
            **{key:row[key] for key in ("window_ms", "checkpoint_validations", "checkpoint_validate_ms",
                "sqlite_calls_ms", "sqlite_file_bytes_before", "sqlite_file_bytes_after")})
        parent = dict(parent_pid=100, owner_pid=200, child_exit_code=0, errors=[], peak_rss_bytes=40,
            asgi_lifecycle=dict(startup_failed=False, shutdown_failed=False, error_occurred=False),
            delivery_received_at=[1 + row["delivery_complete_ms"][0] / 1000], public_oracle=row["oracle"]["public"],
            reconstruction_segments=row["reconstruction_segments"][1:],
            **{key:row[key] for key in ("variant", "population", "windows", "seed_files", "network")})
        owner['delivery_confirmations'] = [dict(tick=1, received_at=parent['delivery_received_at'][0], actor_count=100)]
        cost.write_json(cost._delivery_ack_path(folder, 1), owner['delivery_confirmations'][0])
        ready = dict(owner_pid=200, variant=variant, population=100, windows=1,
            initial_tick=0, clock_profile="manual_window_cost")
        for name, raw in (("owner-ready", ready), ("owner-result", owner), ("parent-observed", parent)):
            cost.write_json(folder / (name + ".json"), raw)
        row = cost.merge_process_evidence(ready, owner, parent)
        rows[variant] = row
        cost.write_json(folder / "result.json", row)
    for variant in ("before", "after"):
        cost.write_json(tmp_path / f"transport-{variant}.json", {"runs": [rows[variant]]})
    manifest = dict(schema_version=1, base_commit="a" * 40, source=source, population=100, windows=1, repeats=1,
        clock_profile="manual_window_cost", formal_cost_matrix=False, status="smoke_checked", comparison=cost.compare_runs([rows["before"]], [rows["after"]]),
        full_transport=rows["full"]["network"])

    def save():
        manifest["raw_artifacts"] = {p.relative_to(tmp_path).as_posix():cost.digest(p.read_bytes())
            for p in tmp_path.rglob("*") if p.is_file() and p.name != "manifest.json"}
        cost.write_json(tmp_path / "manifest.json", manifest)

    save()
    assert cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)["status"] == "smoke_checked"
    from copy import deepcopy
    authority = deepcopy(rows["before"]["oracle"]["authority"])
    invalid = [None, [], {**authority, "confirmed_tick": 2}, {**authority, "authority_head": True},
        {**authority, "population": 1000}, {**authority, "advanced_count": 99},
        {**authority, "confirmed_tick": True}, {**authority, "authority_head": -1},
        {**authority, "population": 100.0}, {**authority, "advanced_count": True}]
    for key in authority:
        if key.endswith("digest"):
            invalid.extend([{k:v for k,v in authority.items() if k != key}, {**authority, key: "invalid"},
                {**authority, key: ("sha256:" + "a" * 64) if key == "gameplay_replay_digest" else "a" * 64}])
    for changed in [*invalid, authority]:
        for variant, row in rows.items():
            row["oracle"]["authority"] = changed
            folder = variant if variant == "full" else variant + "-0"
            cost.write_json(tmp_path / folder / "result.json", row)
            owner_path = tmp_path / folder / "owner-result.json"
            owner = json.loads(owner_path.read_text(encoding="utf-8"))
            owner["authority"] = changed
            cost.write_json(owner_path, owner)
            if variant != "full":
                cost.write_json(tmp_path / f"transport-{variant}.json", {"runs": [row]})
        save()
        if changed is not authority:
            with pytest.raises(ValueError, match="authority"):
                cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)
        else:
            assert cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)["status"] == "smoke_checked"
    with pytest.raises(ValueError, match="formal"):
        cost.verify_artifacts(tmp_path, expected_commit="a" * 40)
    with pytest.raises(ValueError, match="identity"):
        cost.verify_artifacts(tmp_path, expected_commit="b" * 40, require_formal=False)
    manifest["source"] = {"source_sha256": "stale"}
    save()
    with pytest.raises(ValueError, match="identity"):
        cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)
    manifest["source"] = source
    manifest["comparison"]["after_window_ms"]["median"] = 0
    save()
    with pytest.raises(ValueError, match="comparison"):
        cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)
    manifest["comparison"] = cost.compare_runs([rows["before"]], [rows["after"]])
    for name, change in (
        ("delivery-ack-1", None),
        ("delivery-ack-1", {"tick": 2}),
        ("owner-ready", None),
        ("owner-result", None),
        ("parent-observed", None),
        ("owner-ready", {"owner_pid": 201}),
        ("owner-result", {"errors": ["CancelledError"]}),
        ("owner-result", {"window_started": [2.]}),
        ("owner-result", {"peak_rss_bytes": 0}),
        ("owner-result", {"delivery_confirmations": []}),
        ("owner-result", {"delivery_confirmations": [dict(tick=1, received_at=1.008, actor_count=99)]}),
        ("parent-observed", {"child_exit_code": True}),
        ("parent-observed", {"asgi_lifecycle": dict(startup_failed=False, shutdown_failed=True, error_occurred=False)}),
        ("parent-observed", {"delivery_received_at": [3.]}),
        ("result", {"process_peak_rss_bytes": 1}),
    ):
        raw_path = tmp_path / "after-0" / (name + ".json")
        original_raw = raw_path.read_bytes()
        if change is None:
            raw_path.unlink()
        else:
            cost.write_json(raw_path, dict(json.loads(original_raw), **change))
        save()
        with pytest.raises(ValueError, match="artifact|process|owner"):
            cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)
        raw_path.write_bytes(original_raw)
    save()
    # 即便确认身份正确，下一窗在上一窗全部收包前开始也必须拒绝。
    ready = json.loads((tmp_path / 'after-0/owner-ready.json').read_text())
    owner = json.loads((tmp_path / 'after-0/owner-result.json').read_text())
    parent = json.loads((tmp_path / 'after-0/parent-observed.json').read_text())
    for row in (ready, owner, parent): row['windows'] = 2
    owner['window_started'] = [1., 1.005]
    parent['delivery_received_at'] = [1.01, 1.02]
    owner['delivery_confirmations'] = [dict(tick=i+1, received_at=t, actor_count=100)
        for i, t in enumerate(parent['delivery_received_at'])]
    with pytest.raises(ValueError, match='clock'):
        cost.merge_process_evidence(ready, owner, parent)
    trace_path = tmp_path / "after-0/public-messages.jsonl"
    original = trace_path.read_text(encoding="utf-8")
    # 更新 manifest hash 也不能把删除一个真实窗口的消息包装成完整证据。
    trace_path.write_text("\n".join(original.splitlines()[:-1]) + "\n", encoding="utf-8")
    save()
    with pytest.raises(ValueError):
        cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)
    trace_path.write_text(original, encoding="utf-8")
    save()
    trace_path.unlink()
    with pytest.raises(ValueError, match="artifact"):
        cost.verify_artifacts(tmp_path, expected_commit="a" * 40, require_formal=False)


def test_each_delivery_ack_can_publish_while_previous_file_is_open(tmp_path):
    import os
    from scripts.verification import verify_population_transport_cost as cost
    first = cost._delivery_ack_path(tmp_path, 1)
    second = cost._delivery_ack_path(tmp_path, 2)
    one = dict(tick=1, received_at=1.0, actor_count=160)
    two = dict(tick=2, received_at=2.0, actor_count=160)
    cost.write_json(first, one)
    handle = None
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        native = ctypes.WinDLL('kernel32', use_last_error=True)
        native.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
        native.CreateFileW.restype = wintypes.HANDLE
        native.CloseHandle.argtypes = (wintypes.HANDLE,)
        # 保留真实读句柄且不允许删除/替换，确定性模拟child读取上一窗确认。
        handle = native.CreateFileW(str(first), 0x80000000, 1, None, 3, 0, None)
        assert handle != ctypes.c_void_p(-1).value
    try:
        cost.write_json(second, two)
        assert first != second
        assert json.loads(first.read_text()) == one
        assert json.loads(second.read_text()) == two
    finally:
        if handle is not None:
            native.CloseHandle(handle)
