import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import pytest

from scripts.verification.population_godot_runner import child_environment, write_json, source_manifest, wait_file, stop_owned
from scripts.verification.verify_population_godot_runtime import ROOT, validate_lod_boundary, validate_capture, validate_png


def _boundary(path, population=1000):
    refs = [f"character:resident_{i:05}" for i in range(population)]
    visible = min(160, population)
    counts = dict(near=32, far=visible - 32, invisible=population - visible, active_marker_count=visible)
    authority = dict(driver_id=1, world_id=2, confirmed_tick=70, population=population,
                     advanced_count=population, receipt_digest="sha256:receipt", checkpoint_digest="sha256:checkpoint",
                     character_revision_digest="sha256:revisions", population_state_digest="sha256:state",
                     gameplay_replay_digest="sha256:replay", owner_receipt_digest="sha256:receipts",
                     gameplay_events_digest="sha256:events", hot_revision_digest="sha256:hot",
                     stream_revision_digest="sha256:streams", authority_head=10)
    for name, start in (("before", 0), ("after", 32)):
        members = refs[:visible] if population == 100 else refs[start:start + visible]
        write_json(path / f"authority-{name}.json", dict(authority=authority,
                   subscriptions=members, scheduling_paused=True, resumed_same_driver=name == "after"))
        write_json(path / f"lod-{name}.json", dict(members=members, near_members=refs[start:start + 32],
                   counts=counts, confirmed_tick=70, camera_position=[start, 27, 34], elapsed_us=1000000 + start))
    return set(refs)


def test_same_owner_boundary_requires_all_population_and_a_real_membership_rotation(tmp_path):
    refs = _boundary(tmp_path)
    assert validate_lod_boundary(tmp_path, refs)["authority_unchanged"]
    after = json.loads((tmp_path / "authority-after.json").read_text())
    after["authority"]["character_revision_digest"] = "changed"
    write_json(tmp_path / "authority-after.json", after)
    with pytest.raises(ValueError, match="lod_authority_changed"):
        validate_lod_boundary(tmp_path, refs)


@pytest.mark.parametrize("field,value", [("advanced_count", 160), ("confirmed_tick", 0)])
def test_lod_proof_cannot_advance_only_visible_population(tmp_path, field, value):
    refs = _boundary(tmp_path)
    for name in ("before", "after"):
        path = tmp_path / f"authority-{name}.json"
        data = json.loads(path.read_text())
        data["authority"][field] = value
        write_json(path, data)
    with pytest.raises(ValueError, match="lod_authority_invalid"):
        validate_lod_boundary(tmp_path, refs)


def test_child_environment_never_inherits_provider_secrets_or_python_startup_hooks():
    env = child_environment({"PATH": "system", "SystemRoot": "C:/Windows", "OPENAI_API_KEY": "secret",
                             "SIMING_LLM_API_KEY": "secret", "PYTHONSTARTUP": "bad.py", "PYTHONPATH": "bad"})
    assert env["PATH"] == "system" and env["SystemRoot"] == "C:/Windows"
    assert "secret" not in env.values() and "PYTHONSTARTUP" not in env
    assert env["PYTHONHASHSEED"] == "0"


def test_source_manifest_covers_godot_python_scene_and_ignores_dotenv(tmp_path):
    for name in ("backend/app/main.py", "scripts/phase0/PopulationProbe.gd", "scenes/phase0/PopulationProbe.tscn", "project.godot"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original\n", encoding="utf-8")
    before = source_manifest(tmp_path)
    (tmp_path / ".env").write_text("API_KEY=secret")
    assert source_manifest(tmp_path) == before
    (tmp_path / "scripts/phase0/PopulationProbe.gd").write_text("changed\n")
    assert source_manifest(tmp_path)["source_sha256"] != before["source_sha256"]


def test_self_reported_capture_cannot_pass_without_raw_evidence(tmp_path):
    write_json(tmp_path / "godot-capture.json", {"status": "captured", "godot_status": "runtime_verified"})
    with pytest.raises((ValueError, FileNotFoundError, KeyError)):
        validate_capture(tmp_path, 100)


def test_missing_external_engine_writes_failed_manifest_without_running_godot(tmp_path, monkeypatch):
    from scripts.verification import population_godot_runner as runner
    monkeypatch.setattr(runner, "source_manifest", lambda: dict(source_sha256="sha256:test", files={}))
    monkeypatch.setattr(runner.platform, "python_version", lambda: "3.12.14")
    output = tmp_path / "capture"
    result = runner.collect(output, tmp_path / "not-installed-godot.exe")
    assert result["status"] == "failed" and result["godot_status"] == "godot_unverified"
    assert json.loads((output / "manifest.json").read_text())["cases"] == {}
    assert result["collector_pid"] == runner.os.getpid()


@pytest.mark.parametrize("status,expected", [("passed", 0), ("failed", 2)])
def test_harness_cli_uses_unique_external_capture_and_preserves_status(tmp_path, monkeypatch, status, expected):
    import sys
    from scripts.verification import population_godot_runner as runner
    from scripts.verification import verify_population_godot_runtime as verify

    called = []
    def capture(output, godot):
        output.mkdir(parents=True, exist_ok=False)
        called.append((output, godot))
        return {"status": status, "godot_status": "runtime_verified" if status == "passed" else "godot_unverified"}

    monkeypatch.setattr(runner, "collect", capture)
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["verify", "--godot-exe", str(tmp_path / "external.exe"), "--python-exe", sys.executable])
    assert verify.main() == expected
    first = called[0][0]
    assert verify.main() == expected
    assert first != called[1][0]
    assert first.parent == tmp_path / ".harness/verification"
    summary = json.loads((tmp_path / ".harness/verification/population-godot-runtime-report.json").read_text(encoding="utf-8"))
    assert summary["overall_population_godot_runtime_passed"] is (expected == 0)
    assert summary["godot_status"] == ("runtime_verified" if expected == 0 else "godot_unverified")
    assert summary["manifest"] == str(called[1][0] / "manifest.json")


def _png(path, *, width=1280, red=0):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, 720, 8, 2, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress((b"\0" + bytes((red, 20, 30)) * width) * 720)) + chunk(b"IEND", b""))


def test_png_gate_checks_dimensions_crc_and_complete_compressed_image(tmp_path):
    path = tmp_path / "image.png"
    _png(path)
    assert validate_png(path).startswith("sha256:")
    original = path.read_bytes()
    for bad in (original[:-1], original[:45] + b"changed" + original[52:], original + b"trailing"):
        path.write_bytes(bad)
        with pytest.raises(ValueError, match="screenshot_png_invalid"):
            validate_png(path)
    _png(path, width=640)
    with pytest.raises(ValueError, match="screenshot_png_invalid"):
        validate_png(path)


def _capture_fixture(path, *, short_trace=False):
    from test_population_godot_evidence import _frames, _trace, _append_delta
    from scripts.verification.verify_population_godot_runtime import validate_messages
    refs = _trace(path, mutate=_append_delta)
    counts = dict(near=32, far=68, invisible=0, active_marker_count=100)
    observations = [json.loads(line) for line in (path / "observations.jsonl").read_text().splitlines()]
    for row in observations:
        if "screenshot" in row:
            row["counts"] = counts
    (path / "observations.jsonl").write_text("".join(json.dumps(row) + "\n" for row in observations))
    if not short_trace:
        for name in ("messages", "observations"):
            file = path / f"{name}.jsonl"
            rows = [json.loads(line) for line in file.read_text().splitlines()]
            for row in rows:
                if row.get("screenshot") == "after.png":
                    row["elapsed_us"] = 70_100_020
                elif row["elapsed_us"] > 201_010:
                    row["elapsed_us"] += 72_000_000
                elif row["elapsed_us"] > 100_010:
                    row["elapsed_us"] += 20_000_000
            file.write_text("".join(json.dumps(row) + "\n" for row in rows))
    _frames(path / "frame-times.csv", mutate=lambda rows: [row.update(
        confirmed_tick=2 if 10_100_000 + row["elapsed_us"] >= 20_102_010 else 1) for row in rows])
    # 仅门禁单测合成证据，永不作为外机运行报告发布。
    _boundary(path, 100)
    for name in ("before", "after"):
        for prefix in ("lod", "authority"):
            file = path / f"{prefix}-{name}.json"
            data = json.loads(file.read_text())
            for key in ("members", "near_members", "subscriptions"):
                if key in data:
                    data[key] = [actor.replace("resident_00", "resident_") for actor in data[key]]
            if prefix == "lod" and not short_trace:
                data["elapsed_us"] = 71_000_000 + (32 if name == "after" else 0)
            write_json(file, data)
    write_json(path / "roster.json", dict(actor_ids=sorted(ref.removeprefix("character:") for ref in refs)))
    for name, red in (("before.png", 20), ("after.png", 80)):
        _png(path / name, red=red)
    capture = dict(status="captured", godot_status="godot_unverified", population=100,
        godot_version=dict(major=4, minor=6, patch=3, status="stable"), renderer="forward_plus", driver="vulkan",
        resolution=[1280, 720], vsync=0, scene="res://scenes/phase0/PopulationProbe.tscn", gpu="synthetic-test-fixture",
        warmup_us=10_000_000, sample_count=3000, sample_duration_us=60_000_000, counts=counts,
        ready_elapsed_us=100_000, sample_start_elapsed_us=10_100_000,
        sample_end_elapsed_us=70_100_000, capture_end_elapsed_us=73_000_000,
        first_tick=1, last_tick=2, application_packet_bytes=validate_messages(path, refs)["application_packet_bytes"],
        gap_seen=True, resync_recovered=True, rotation_complete=True, reconnect_complete=True)
    write_json(path / "godot-capture.json", capture)


def test_complete_synthetic_capture_gate_then_rejects_missing_or_mismatched_evidence(tmp_path):
    _capture_fixture(tmp_path)
    assert validate_capture(tmp_path, 100)["messages"]["applied_delta_count"] == 1
    capture = json.loads((tmp_path / "godot-capture.json").read_text())
    for change, error in ((dict(driver="opengl3"), "render_capture_invalid"),
                          (dict(sample_count=2999), "capture_sample_mismatch"),
                          (dict(warmup_us=1), "capture_sample_mismatch"),
                          (dict(application_packet_bytes={}), "capture_packet_mismatch"),
                          (dict(first_tick=999), "capture_tick_mismatch")):
        write_json(tmp_path / "godot-capture.json", {**capture, **change})
        with pytest.raises(ValueError, match=error):
            validate_capture(tmp_path, 100)
    write_json(tmp_path / "godot-capture.json", capture)
    (tmp_path / "after.png").unlink()
    with pytest.raises(FileNotFoundError):
        validate_capture(tmp_path, 100)


def test_real_backend_child_pauses_same_driver_for_lod_without_godot(tmp_path):
    """仅验证外机runner的真实后端控制路径，不生成Godot通过证据。"""
    from websockets.sync.client import connect
    from scripts.launch_trusted_local_gameplay_mirror import request_enrollment
    output, state = tmp_path / "output", tmp_path / "state"
    output.mkdir()
    state.mkdir()
    write_json(output / "roster.json", dict(actor_ids=[f"resident_{index:05d}" for index in range(100)]))
    environment = child_environment()
    environment["GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET"] = "test-local-launch-secret"
    command = [sys.executable, str(ROOT / "scripts/verification/verify_population_godot_runtime.py"),
               "--backend-child", str(output), "--state-directory", str(state)]
    with (output / "backend.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        try:
            ready = wait_file(output / "backend-ready.json", process, timeout=90)
            enrollment = request_enrollment(backend_http_url=f"http://127.0.0.1:{ready['port']}",
                launch_profile_ref="population-render-probe", launcher_secret=environment["GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET"])
            with connect(f"ws://127.0.0.1:{ready['port']}/ws", compression=None) as socket:
                socket.send(json.dumps(dict(message_type="websocket_session_bind", payload=enrollment.model_dump(mode="json"))))
                assert json.loads(socket.recv(timeout=10))["payload"]["accepted"]
                assert json.loads(socket.recv(timeout=10))["message_type"] == "websocket_session_bound"
                def request(kind, actor):
                    socket.send(json.dumps(dict(message_type=kind, payload=dict(actor_ref=actor))))
                    while True:
                        message = json.loads(socket.recv(timeout=10))
                        if message["message_type"] == "ack":
                            assert message["payload"]["accepted"]
                            return
                request("gameplay_mirror_subscribe", "character:resident_00000")
                # 首份tick0加首个更新会丢弃；等待真实clock确认后的后续消息。
                while True:
                    wire = json.loads(socket.recv(timeout=10))
                    if wire["message_type"] == "gameplay_mirror_delivery" and wire["payload"]["payload"]["groups"]["population_public"]["payload"]["confirmed_tick"] > 0:
                        break
                write_json(output / "stage.json", dict(stage="awaiting_lod_boundary"))
                before = wait_file(output / "authority-before.json", process, timeout=30)
                request("gameplay_mirror_unsubscribe", "character:resident_00000")
                request("gameplay_mirror_subscribe", "character:resident_00001")
                write_json(output / "stage.json", dict(stage="lod_rotated"))
                after = wait_file(output / "authority-after.json", process, timeout=30)
                assert before["authority"] == after["authority"]
                assert after["resumed_same_driver"] is True
                assert before["subscriptions"] != after["subscriptions"]
                assert before["authority"]["advanced_count"] == 100
            (state / "stop").touch()
            assert process.wait(15) == 0
            assert not (output / "godot-capture.json").exists()
        finally:
            (state / "stop").touch()
            stop_owned(process)


def test_render_owner_probe_pauses_and_resumes_original_spawn_driver_without_godot(tmp_path, monkeypatch):
    """只执行 Python owner；不把后端截面测试当作 Godot 渲染通过。"""
    import asyncio
    import os
    from app.config import Settings
    from app.services import runtime_process
    from scripts.verification.population_godot_runner import render_owner_child
    state = tmp_path / 'state'
    state.mkdir()
    write_json(tmp_path / 'roster.json', dict(actor_ids=['char_a', 'char_b', 'char_c']))
    settings = Settings(heavenly_graph_path=str(state / 'graph.sqlite3'),
        population_roster_path=str(tmp_path / 'roster.json'), population_runtime_profile='benchmark_1x',
        dialogue_mode='stub', character_model_provider_kind='local', siming_llm_mode='disabled',
        character_model_endpoint=None, character_model_api_key=None, character_model_model=None)
    monkeypatch.setattr(sys, 'argv', [*sys.argv, '--backend-child', str(tmp_path), '--state-directory', str(state)])
    monkeypatch.setattr(runtime_process, 'CHILD_TARGET', render_owner_child)

    async def run():
        host = runtime_process.RuntimeProcess(settings.model_dump_json())
        async def read(name):
            from scripts.verification.verify_population_mixed_soak import read_control
            async with asyncio.timeout(30):
                while not (tmp_path / name).exists():
                    assert host.process.is_alive()
                    if (tmp_path / 'owner-observed.json').exists():
                        assert not (await read_control(tmp_path / 'owner-observed.json'))['errors']
                    await asyncio.sleep(.02)
            return await read_control(tmp_path / name)
        try:
            await host.start()
            ready = await read('owner-ready.json')
            assert ready['owner_pid'] == host.process.pid != os.getpid()
            assert ready['population'] == 3
            await asyncio.sleep(1.2)
            write_json(tmp_path / 'stage.json', dict(stage='awaiting_lod_boundary'))
            before = await read('authority-before.json')
            write_json(tmp_path / 'stage.json', dict(stage='lod_rotated'))
            after = await read('authority-after.json')
            assert before['authority'] == after['authority']
            assert before['owner_pid'] == after['owner_pid'] == host.process.pid
            assert before['authority']['confirmed_tick'] >= 1
            assert before['authority']['advanced_count'] == 3
            assert after['resumed_same_driver']
            (state / 'stop').touch()
            observed = await read('owner-observed.json')
            assert observed['owner_pid'] == host.process.pid and observed['errors'] == []
        finally:
            await host.close()
        assert host.process.exitcode == 0
        assert not (tmp_path / 'godot-capture.json').exists()
    asyncio.run(run())


def test_render_backend_evidence_requires_real_child_and_clean_lifecycle(tmp_path):
    from copy import deepcopy
    from scripts.verification.verify_population_godot_runtime import validate_backend_process
    originals = {
        'backend-ready.json': dict(parent_pid=100, owner_pid=101, population=100, clock_profile='benchmark_1x'),
        'owner-ready.json': dict(owner_pid=101, population=100, clock_profile='benchmark_1x'),
        'owner-observed.json': dict(owner_pid=101, errors=[]),
        'authority-before.json': dict(owner_pid=101),
        'authority-after.json': dict(owner_pid=101),
        'backend-observed.json': dict(parent_pid=100, owner_pid=101, child_exit_code=0, errors=[],
            asgi_lifecycle=dict(startup_failed=False, shutdown_failed=False, error_occurred=False))}
    def save(rows):
        for name, row in rows.items():
            write_json(tmp_path / name, row)
    save(originals)
    validate_backend_process(tmp_path, 100, 100)
    for name, field, value in [('owner-ready.json', 'owner_pid', 100),
            ('owner-ready.json', 'population', 1000), ('owner-observed.json', 'owner_pid', 102),
            ('owner-observed.json', 'errors', ['cancelled']), ('backend-observed.json', 'child_exit_code', None),
            ('authority-after.json', 'owner_pid', 100),
            ('backend-observed.json', 'child_exit_code', False), ('backend-observed.json', 'parent_pid', 102),
            ('backend-observed.json', 'errors', ['parent_failure']),
            ('backend-observed.json', 'asgi_lifecycle', dict(startup_failed=False, shutdown_failed=True, error_occurred=False))]:
        rows = deepcopy(originals)
        rows[name][field] = value
        save(rows)
        with pytest.raises(ValueError, match='backend_process'):
            validate_backend_process(tmp_path, 100, 100)


def test_short_trace_cannot_claim_seventy_second_capture(tmp_path):
    _capture_fixture(tmp_path, short_trace=True)
    with pytest.raises(ValueError, match='capture_timeline'):
        validate_capture(tmp_path, 100)


def test_source_manifest_covers_actual_profiles_and_approved_package_manifests(tmp_path):
    if sys.platform == "win32" and not str(tmp_path).startswith("\\\\?\\"):
        tmp_path = Path("\\\\?\\" + str(tmp_path.resolve()))
    from app.gameplay.production_package_registry import _APPROVED_MANIFESTS
    files = ['assets/characters/profiles/char_a.yaml', *[
        'docs/superpowers/specs/world-character-siming-authority-mainline/' + name for name in _APPROVED_MANIFESTS]]
    for name in files:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('original', encoding='utf-8')
    original = source_manifest(tmp_path)
    assert set(files) <= set(original['files'])
    for name in files:
        path = tmp_path / name
        path.write_text('changed', encoding='utf-8')
        assert source_manifest(tmp_path)['source_sha256'] != original['source_sha256']
        path.write_text('original', encoding='utf-8')


@pytest.mark.parametrize('field,value', [
    ('sample_start_elapsed_us', 10_100_001), ('sample_end_elapsed_us', 70_100_001),
    ('capture_end_elapsed_us', 72_000_000), ('ready_elapsed_us', 100_011),
])
def test_capture_rejects_inconsistent_or_truncated_common_timeline(tmp_path, field, value):
    _capture_fixture(tmp_path)
    path = tmp_path / 'godot-capture.json'
    capture = json.loads(path.read_text())
    capture[field] = value
    write_json(path, capture)
    with pytest.raises(ValueError, match='capture_timeline'):
        validate_capture(tmp_path, 100)


def test_capture_csv_ticks_must_match_markers_at_absolute_sample_time(tmp_path):
    _capture_fixture(tmp_path)
    path = tmp_path / 'frame-times.csv'
    lines = path.read_text().splitlines()
    values = lines[2].split(',')
    values[-1] = '999'
    lines[2] = ','.join(values)
    path.write_text('\n'.join(lines) + '\n')
    with pytest.raises(ValueError, match='capture_timeline_frame_marker_mismatch'):
        validate_capture(tmp_path, 100)


def test_capture_allows_delayed_after_screenshot_with_same_verified_anchor(tmp_path):
    _capture_fixture(tmp_path)
    path = tmp_path / 'observations.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    next(row for row in rows if row.get('screenshot') == 'after.png')['elapsed_us'] += 500_000
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    assert validate_capture(tmp_path, 100)['status'] == 'passed'


@pytest.mark.parametrize('concurrent_stop', [True, False])
def test_render_stop_guard_distinguishes_normal_cross_process_publication(tmp_path, monkeypatch, concurrent_stop):
    import asyncio
    from types import SimpleNamespace
    from scripts.verification.population_godot_runner import _wait_for_render_stop
    observed, stop = tmp_path / 'owner-observed.json', tmp_path / 'stop'
    observed.write_text('{"owner_pid":101,"errors":[]}', encoding='utf-8')
    original = Path.exists
    def exists(path):
        # 原 while guard 已读到 stop 不存在；child 的正常结束记录随后才可见。
        if path == observed and concurrent_stop:
            stop.touch()
        return original(path)
    monkeypatch.setattr(Path, 'exists', exists)
    awaitable = _wait_for_render_stop(tmp_path, tmp_path, SimpleNamespace(done=lambda: False),
                                     SimpleNamespace(is_alive=lambda: True))
    if concurrent_stop:
        asyncio.run(awaitable)
        assert stop.exists()
    else:
        with pytest.raises(RuntimeError, match='observation_ended_early'):
            asyncio.run(awaitable)


@pytest.mark.parametrize("failure", [None, "restore", "verify", "seal"])
def test_collect_verifies_only_after_qos_restore_and_sealing(tmp_path, monkeypatch, failure):
    from scripts.verification import population_godot_runner as runner
    from contextlib import contextmanager
    from scripts.verification import population_process_qos as policy
    from scripts.verification import verify_population_godot_runtime as gate
    output = tmp_path / "capture"
    calls = []
    @contextmanager
    def scope(path):
        yield
        runner.write_json(path, {"restored": True})
        calls.append("restored")
        if failure == "restore": raise OSError("restore_failed")
    monkeypatch.setattr(policy, "recorded_high_qos", scope)
    def capture(directory, godot):
        result = {"status": "passed", "godot_status": "runtime_verified"}
        runner.write_json(directory / "manifest.json", result)
        return result
    monkeypatch.setattr(runner, "_collect_with_policy", capture)
    def verify(directory):
        assert calls == ["restored"]
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        assert "collector-qos.json" in manifest["artifacts"]
        calls.append("verified")
        if failure == "verify": raise ValueError("bad_evidence")
    monkeypatch.setattr(gate, "verify_artifacts", verify)
    if failure == "seal":
        def broken_digest(_): raise OSError("seal_failed")
        monkeypatch.setattr(runner, "digest", broken_digest)
    if failure in {"restore", "seal"}:
        with pytest.raises(OSError, match=f"{failure}_failed"):
            runner.collect(output, tmp_path / "unused")
    else:
        result = runner.collect(output, tmp_path / "unused")
        assert result["status"] == ("failed" if failure else "passed")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == ("failed" if failure else "passed")
    assert calls == (["restored"] if failure in {"restore", "seal"} else ["restored", "verified"])
    if failure:
        assert manifest["godot_status"] == "godot_unverified"
