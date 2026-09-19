"""广泛 harness 的封存/离线检查；合成日志不作为真实 Godot 证据。"""
from __future__ import annotations

import json
from pathlib import Path
import hashlib
import shutil

import pytest

from scripts.verification import verify_population_harness_evidence as gate
from scripts.verification.population_godot_runner import write_json
from scripts.verification.check_change_lifecycle import REQUIRED_RULE_IDS


SHA = "a" * 40


@pytest.mark.parametrize('name,content', [
    ('siming-heavenly.sqlite3.gameplay.json', b'SQLite format 3\x00' + b'x' * 4096),
    ('siming-heavenly.sqlite3.gameplay.json', b'{"legacy":true}'),
    ('renamed-report.json', b'SQLite format 3\x00' + b'x' * 4096),
], ids=['gameplay_sqlite', 'legacy_storage_json', 'renamed_sqlite'])
def test_raw_excludes_storage_names_and_sqlite_magic(tmp_path, name, content):
    if content.startswith(b'SQLite format 3\x00'):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(tmp_path / name)) as connection, connection:
            connection.execute('CREATE TABLE actual_gameplay_data (id INTEGER)')
    else:
        (tmp_path / name).write_bytes(content)
    (tmp_path / 'real-report.json').write_text('{"passed":true}', encoding='utf-8')
    (tmp_path / 'real.log').write_text('original output', encoding='utf-8')
    assert set(gate._files(tmp_path)) == {'real-report.json', 'real.log'}
    assert set(gate._raw(tmp_path)) == {'real-report.json', 'real.log'}


def test_capture_rejects_repo_or_existing_output_before_creating_evidence(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    monkeypatch.setattr(gate, 'ROOT', root)
    inside = root / '.harness/verification/invalid'
    with pytest.raises(ValueError):
        gate.collect(inside, profile='change-lifecycle')
    assert not inside.exists()
    existing = tmp_path / 'owned-by-someone-else'
    existing.mkdir()
    (existing / 'keep.txt').write_text('preserve', encoding='utf-8')
    with pytest.raises(ValueError):
        gate.collect(existing, profile='change-lifecycle')
    assert (existing / 'keep.txt').read_text(encoding='utf-8') == 'preserve'


def test_exported_run_scope_evidence_is_verified_without_repo_archive(capture, monkeypatch):
    root, latest, output, _ = capture
    run_id = 'a' * 32
    def exported(command, *, cwd, env, log, timeout):
        export = Path(command[command.index('--export-evidence') + 1])
        attempt = export / 'profiles/change-lifecycle/1'
        attempt.mkdir(parents=True)
        (attempt / 'command.log').write_text('original child stdout', encoding='utf-8')
        command_profile = [command[0], str(root / 'scripts/verification/change-lifecycle.py')]
        report = dict(overall_change_lifecycle_passed=True,
            results=[dict(id=key, status='proved', evidence=['AGENTS.md']) for key in sorted(REQUIRED_RULE_IDS)])
        write_json(attempt / 'change-lifecycle-report.json', report)
        row = dict(run_id=run_id, profile='change-lifecycle', command=command_profile,
            attempt=1, attempts=1, exit_code=0, status='passed')
        write_json(attempt / 'profile-result.json', row)
        summary = dict(schema_version=2, run_id=run_id, suite_id='change-lifecycle',
            revision=SHA, overall_harness_passed=True, cleanup_status='passed',
            profiles=[row], not_executed=[])
        write_json(export / 'harness-run-report.json', summary)
        write_json(export / 'run-manifest.json', {**summary,
            'profile_exit_codes': [dict(profile='change-lifecycle', exit_code=0)]})
        log.write_text('harness_profile=change-lifecycle status=passed failure=None\n', encoding='utf-8')
        return 0
    monkeypatch.setattr(gate, 'run_logged', exported)
    result = gate.collect(output, profile='change-lifecycle')
    assert result['status'] == 'passed'
    assert not latest.exists()
    assert gate.verify_artifacts(output, expected_commit=SHA, profile='change-lifecycle')['passed']


@pytest.fixture
def capture(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    latest = root / ".harness/verification"
    profile_dir = root / ".harness/profiles"
    profile_dir.mkdir(parents=True)
    script_dir = root / "scripts/verification"
    script_dir.mkdir(parents=True)
    for name, godot in (("change-lifecycle", False), ("mainline-unified-runtime", True)):
        (script_dir / f"{name}.py").write_text("", encoding="utf-8")
        write_json(profile_dir / f"{name}.json", dict(schema_version=1, name=name,
            script=f"scripts/verification/{name}.py", requires_godot=godot, max_attempts=2))
    monkeypatch.setattr(gate, "ROOT", root)
    monkeypatch.setattr(gate, "_identity", lambda expected: ({}, {"files": {}, "source_sha256": "b" * 64}))
    monkeypatch.setattr(gate, "git_head", lambda root: SHA)
    monkeypatch.setattr(gate, "harness_inputs", lambda: {"AGENTS.md": "c" * 64})
    monkeypatch.setattr(gate, "environment", lambda: {"godot": "not_run"})

    def run(command, *, cwd, env, log, timeout):
        selection = command[command.index("--profile") + 1]
        names = [selection] if selection != "all" else ["change-lifecycle", "mainline-unified-runtime"]
        run_id = "a" * 32
        export = Path(command[command.index('--export-evidence') + 1])
        export.mkdir(parents=True)
        rows = []
        for name in names:
            args = [command[0], str(root / f"scripts/verification/{name}.py")]
            if name == "mainline-unified-runtime":
                args += ["--godot-exe", command[command.index("--godot-exe") + 1], "--python-exe", command[0]]
            attempt = export / 'profiles' / name / '1'
            attempt.mkdir(parents=True)
            (attempt / 'command.log').write_text('original child stdout', encoding='utf-8')
            payload = {f"overall_{name.replace('-', '_')}_passed": True}
            if name == 'change-lifecycle':
                payload['results'] = [dict(id=key, status='proved', evidence=['AGENTS.md']) for key in sorted(REQUIRED_RULE_IDS)]
            elif name == 'mainline-unified-runtime':
                payload.update(results=[], artifacts={})
                for key, (artifact, child_log, child_report) in gate.MAINLINE_EVIDENCE.items():
                    (attempt / child_log).write_text('original child stdout', encoding='utf-8')
                    logical = Path.home() / f'paralls-harness-{run_id}' / 'profiles' / name / '1'
                    evidence = [str(logical / child_log)]
                    payload['artifacts'][artifact + '_log'] = evidence[0]
                    if child_report:
                        write_json(attempt / child_report, {f'overall_{key}_passed': True})
                        evidence.append(str(logical / child_report))
                        payload['artifacts'][artifact + '_report'] = evidence[-1]
                    payload['results'].append(dict(id=key, status='proved', evidence=evidence))
            report_file = attempt / f'{name}-report.json'
            write_json(report_file, payload)
            row = dict(run_id=run_id, profile=name, command=args, exit_code=0, status='passed',
                attempt=1, attempts=1, evidence=dict(path=f'profiles/{name}/1/{name}-report.json',
                    sha256=hashlib.sha256(report_file.read_bytes()).hexdigest()))
            write_json(attempt / 'profile-result.json', row)
            rows.append(row)
        report = dict(schema_version=2, run_id=run_id, suite_id=selection, revision=SHA,
            overall_harness_passed=True, cleanup_status='passed', profiles=rows, not_executed=[])
        write_json(export / 'harness-run-report.json', report)
        write_json(export / 'run-manifest.json', {**report,
            'profile_exit_codes': [dict(profile=name, exit_code=0) for name in names]})
        log.write_text('\n'.join(f'harness_profile={name} status=passed failure=None' for name in names), encoding='utf-8')
        return 0

    monkeypatch.setattr(gate, "run_logged", run)
    return root, latest, tmp_path / "evidence", run


@pytest.mark.parametrize('defect', ['missing', 'empty'])
def test_offline_rejects_missing_required_lifecycle_results_after_rehash(capture, defect):
    _, _, output, _ = capture
    assert gate.collect(output, profile='change-lifecycle')['status'] == 'passed'
    path = output / 'artifacts/profiles/change-lifecycle/1/change-lifecycle-report.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    if defect == 'missing':
        report['results'][0]['status'] = 'missing'
    else:
        report['results'] = []
    write_json(path, report)
    exported = output / 'artifacts/harness-run-report.json'
    summary = json.loads(exported.read_text(encoding='utf-8'))
    summary['profiles'][0]['evidence']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(exported, summary)
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    manifest['raw_files'] = gate._raw(output)
    write_json(output / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='required_result'):
        gate.verify_artifacts(output, expected_commit=SHA, profile='change-lifecycle')


@pytest.mark.parametrize('missing', ['mainline-unified-world-runtime.log', 'actor-local-perception-report.json'])
def test_mainline_requires_real_child_log_and_report_even_after_rehash(capture, missing):
    root, _, output, _ = capture
    engine = root / 'godot.exe'
    engine.write_bytes(b'test double')
    assert gate.collect(output, profile='mainline-unified-runtime', godot_exe=engine)['status'] == 'passed'
    (output / 'artifacts/profiles/mainline-unified-runtime/1' / missing).unlink()
    manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
    manifest['raw_files'] = gate._raw(output)
    write_json(output / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='required_raw_file_missing'):
        gate.verify_artifacts(output, expected_commit=SHA, profile='mainline-unified-runtime')


@pytest.mark.parametrize('aggregate', ['gameplay-foundation-all', 'embodied-interaction-foundation-all'])
@pytest.mark.parametrize('defect', ['none', 'log', 'report', 'command', 'exit', 'archive', 'status'])
def test_nested_gameplay_evidence(request, defect, aggregate):
    import tempfile
    tmp_path = Path(tempfile.mkdtemp(prefix='pg-'))
    request.addfinalizer(lambda: shutil.rmtree(tmp_path))
    from pathlib import PureWindowsPath
    from scripts.verification.verify_gameplay_foundation_all import GAMEPLAY_FOUNDATION_PROFILES, PROFILE_OVERALL_KEYS
    registry = gate.load_profile_registry(Path(__file__).resolve().parents[2])
    origin = PureWindowsPath('D:/original/repo')
    python, godot = 'D:\\runtime\\python.exe', 'D:\\tools\\godot.exe'
    run_id = 'b' * 32
    logical = Path.home() / f'paralls-harness-{run_id}' / 'profiles' / aggregate / '1'
    aggregate_dir = tmp_path / 'artifacts/profiles' / aggregate / '1'
    aggregate_dir.mkdir(parents=True)
    payload = dict(overall_gameplay_foundation_all_passed=True,
        dependency_profiles=GAMEPLAY_FOUNDATION_PROFILES, results=[])
    profiles = GAMEPLAY_FOUNDATION_PROFILES
    if aggregate == 'embodied-interaction-foundation-all':
        from scripts.verification import verify_embodied_interaction_foundation_all as embodied
        phases = dict(phase_6_gate_profile=embodied.PHASE_6_GATE_PROFILE,
            phase_6_session_profile=embodied.PHASE_6_SESSION_PROFILE,
            phase_7_handoff_profile=embodied.PHASE_7_HANDOFF_PROFILE,
            phase_7_carry_place_profile=embodied.PHASE_7_CARRY_PLACE_PROFILE)
        profiles = [*embodied.PHASE_PROFILES, *phases.values()]
        payload = dict(overall_embodied_interaction_foundation_all_passed=True,
            phase_profiles=embodied.PHASE_PROFILES, **phases, results=[], phase_6_status='gate_satisfied',
            phase_6_interaction_session_status='backend_websocket_and_godot_live_runtime_verified',
            phase_7_handoff_status='backend_websocket_and_godot_live_runtime_verified',
            phase_7_carry_place_status='backend_websocket_and_godot_live_runtime_verified')
    for child in profiles:
        report_name = registry.profiles[child].get('result_artifact', '').removeprefix('.harness/verification/')
        report = {PROFILE_OVERALL_KEYS.get(child, 'overall_child_passed'): True, 'adventure_basic_required_scenarios_complete': True}
        child_root = aggregate_dir / f'child-{child}'
        attempt = child_root / 'profiles' / child / '1'
        attempt.mkdir(parents=True)
        (attempt / 'command.log').write_text('child process stdout', encoding='utf-8')
        if child == 'gameplay-patch-runtime':
            from scripts.verification.verify_gameplay_patch_runtime import TEST_GROUPS
            logs = {key: str(logical / f'child-{child}' / 'profiles' / child / '1' / f'gameplay-patch-runtime-{key}.log') for key, _, _ in TEST_GROUPS}
            report.update(artifacts=dict(pytest_logs=logs),
                results=[dict(id=key, status='proved', evidence=[value]) for key, value in logs.items()])
            for key in logs:
                (attempt / f'gameplay-patch-runtime-{key}.log').write_text('pytest output', encoding='utf-8')
        if report_name:
            write_json(attempt / report_name, report)
        log_name = f'{aggregate}-{child}.log'
        command = gate._profile_command(child, origin, python, godot, registry.profiles)
        row = dict(run_id=run_id, profile=child, command=command, exit_code=0,
            attempt=1, attempts=1, status='passed',
            evidence=dict(path=f'profiles/{aggregate}/1/child-{child}/profiles/{child}/1/{report_name}',
                          sha256=hashlib.sha256((attempt / report_name).read_bytes()).hexdigest()))
        if child == profiles[0]:
            if defect == 'command':
                row['command'] = command + ['--skip']
            if defect == 'exit':
                row['exit_code'] = 1
        write_json(attempt / 'profile-result.json', row)
        summary = dict(schema_version=2, run_id=run_id, suite_id=child, revision=gate.git_head(gate.ROOT),
            overall_harness_passed=True, cleanup_status='pending', profiles=[row], not_executed=[])
        write_json(child_root / 'harness-run-report.json', summary)
        write_json(child_root / 'run-manifest.json', {**summary,
            'profile_exit_codes': [dict(profile=child, exit_code=0)]})
        log = aggregate_dir / log_name
        log.write_text(f'harness_profile={child} status=passed failure=None\n', encoding='utf-8')
        evidence = [str(logical / log_name)]
        if aggregate == 'gameplay-foundation-all':
            evidence.append(str(logical / f'child-{child}' / 'profiles' / child / '1' / report_name))
        payload['results'].append(dict(id=child, status='missing' if defect == 'status' and child == profiles[0] else 'proved', evidence=evidence))
        if child == profiles[0]:
            if defect == 'log':
                log.unlink()
            elif defect == 'report' and report_name:
                (attempt / report_name).unlink()
            elif defect == 'report':
                (child_root / 'harness-run-report.json').unlink()
            elif defect == 'archive':
                (child_root / 'run-manifest.json').unlink()
    raw = gate._raw(tmp_path)
    def raw_path(name):
        if name not in raw:
            raise ValueError('harness_required_raw_file_missing')
        return tmp_path / name
    def verify():
        gate._profile_report(aggregate, payload, origin=origin, python=python,
            godot=godot, registry=registry, raw_path=raw_path, inputs={}, ancestors=('all', aggregate),
            exported_run_id=run_id)
    if defect == 'none':
        verify()
    else:
        with pytest.raises(ValueError):
            verify()


@pytest.mark.parametrize('defect', ['none', 'log', 'status'])
def test_patch_runtime_requires_original_four_group_logs(tmp_path, defect):
    from scripts.verification.verify_gameplay_patch_runtime import TEST_GROUPS
    origin = gate._path('D:/original/repo')
    logs = {key: str(origin / '.harness/verification' / f'gameplay-patch-runtime-{key}.log') for key, _, _ in TEST_GROUPS}
    payload = dict(overall_gameplay_patch_runtime_passed=True, artifacts=dict(pytest_logs=logs),
        results=[dict(id=key, status='proved', evidence=[value]) for key, value in logs.items()])
    if defect == 'status':
        payload['results'][0]['status'] = 'missing'
    seen = []
    def raw_path(name):
        seen.append(name)
        if defect == 'log':
            raise ValueError('harness_required_raw_file_missing')
        return tmp_path / name
    def verify():
        gate._profile_report('gameplay-patch-runtime', payload, origin=origin, python='D:/python.exe',
            godot=None, registry=None, raw_path=raw_path, inputs={}, ancestors=())
    if defect == 'none':
        verify()
        assert len(seen) == len(TEST_GROUPS)
    else:
        with pytest.raises(ValueError):
            verify()


def test_capture_verifies_moved_evidence_without_starting_process(capture, monkeypatch):
    root, latest, output, _ = capture
    manifest = gate.collect(output, profile="change-lifecycle")
    assert manifest["status"] == "passed"
    assert manifest["godot_status"] == "godot_unverified"
    moved = output.with_name("moved")
    output.rename(moved)
    monkeypatch.setattr(gate, "run_logged", lambda *a, **k: pytest.fail("离线不得运行进程"))
    assert gate.verify_artifacts(moved, expected_commit=SHA, profile="change-lifecycle")["passed"]


def test_all_uses_registry_coverage_and_explicit_engine_for_nested_harness(capture, monkeypatch):
    root, _, output, original = capture
    engine = root / "godot.exe"
    engine.write_bytes(b"test-double-not-an-executable")
    def run(command, **kwargs):
        assert kwargs["env"]["GODOT_EXE"] == str(engine)
        return original(command, **kwargs)
    monkeypatch.setattr(gate, "run_logged", run)
    assert gate.collect(output, profile="all", godot_exe=engine)["status"] == "passed"
    result = gate.verify_artifacts(output, expected_commit=SHA, profile="all")
    assert result["profiles"] == 2
    assert result["godot_status"] == "harness_verified"


def test_existing_retry_contract_keeps_both_attempts(capture, monkeypatch):
    _, _, output, original = capture
    def run(command, **kwargs):
        result = original(command, **kwargs)
        export = Path(command[command.index('--export-evidence') + 1])
        path = export / 'harness-run-report.json'
        report = json.loads(path.read_text(encoding="utf-8"))
        prior = export / 'profiles/change-lifecycle/1'
        second = export / 'profiles/change-lifecycle/2'
        shutil.copytree(prior, second)
        write_json(prior / 'profile-result.json', {**report['profiles'][0], 'attempt': 1,
            'status': 'failed', 'exit_code': 1})
        write_json(second / 'profile-result.json', {**report['profiles'][0], 'attempt': 2,
            'attempts': 2, 'evidence': {'path': 'profiles/change-lifecycle/2/change-lifecycle-report.json',
                'sha256': report['profiles'][0]['evidence']['sha256']}})
        report["profiles"][0]["attempts"] = 2
        report["profiles"][0]["attempt"] = 2
        report["profiles"][0]['evidence']['path'] = 'profiles/change-lifecycle/2/change-lifecycle-report.json'
        write_json(path, report)
        return result
    monkeypatch.setattr(gate, "run_logged", run)
    assert gate.collect(output, profile="change-lifecycle")["status"] == "passed"
    assert gate.verify_artifacts(output, expected_commit=SHA, profile="change-lifecycle")["passed"]


@pytest.mark.parametrize("profile", ["mainline-unified-runtime", "all"])
def test_godot_profiles_require_explicit_executable_before_any_launch(capture, monkeypatch, profile):
    _, _, output, _ = capture
    monkeypatch.setenv("GODOT_EXE", "installed-but-not-authorized.exe")
    monkeypatch.setattr(gate, "run_logged", lambda *a, **k: pytest.fail("不得自动发现并启动Godot"))
    result = gate.collect(output, profile=profile)
    assert result["status"] == "failed"
    assert "explicit_godot_executable_required" in result["error"]


@pytest.mark.parametrize("defect", ["exit", "stale", "no_log", "summary", "profile_order", "attempts", "source_changed"])
def test_capture_keeps_failed_evidence(capture, monkeypatch, defect):
    root, _, output, original = capture

    def broken(command, **kwargs):
        if defect == "stale":
            # 未形成当前 export，旧仓库报告不能补齐。
            (root / '.harness/verification').mkdir(parents=True)
            write_json(root / '.harness/verification/harness-run-report.json', {'overall_harness_passed': True})
            kwargs["log"].write_text('old report exists only in repository\n', encoding='utf-8')
            return 0
        result = original(command, **kwargs)
        export = Path(command[command.index('--export-evidence') + 1])
        archive = export / 'harness-run-report.json'
        report = json.loads(archive.read_text(encoding="utf-8"))
        if defect == "exit":
            return 124
        if defect == "no_log":
            kwargs["log"].write_text("", encoding="utf-8")
        if defect == "summary":
            write_json(export / 'profiles/change-lifecycle/1/change-lifecycle-report.json', {"overall_change_lifecycle_passed": False})
        if defect == "profile_order":
            report["profiles"] = []
        if defect == "attempts":
            report["profiles"][0]["attempts"] = 2
        if defect == "source_changed":
            monkeypatch.setattr(gate, "harness_inputs", lambda: {"AGENTS.md": "d" * 64})
        write_json(archive, report)
        return result

    monkeypatch.setattr(gate, "run_logged", broken)
    manifest = gate.collect(output, profile="change-lifecycle")
    assert manifest["status"] == "failed"
    assert (output / "manifest.json").is_file()
    assert (output / "process.log").is_file()
    with pytest.raises(ValueError):
        gate.verify_artifacts(output, expected_commit=SHA, profile="change-lifecycle")


def test_raw_mutation_and_wrong_profile_or_commit_fail(capture):
    _, _, output, _ = capture
    assert gate.collect(output, profile="change-lifecycle")["status"] == "passed"
    for options in (dict(expected_commit="d" * 40, profile="change-lifecycle"),
                    dict(expected_commit=SHA, profile="all")):
        with pytest.raises(ValueError):
            gate.verify_artifacts(output, **options)
    (output / "process.log").write_text("harness_exit_code=0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="raw"):
        gate.verify_artifacts(output, expected_commit=SHA, profile="change-lifecycle")


def test_failed_child_preserves_raw_before_unexpected_exception(capture, monkeypatch):
    _, _, output, original = capture
    def broken(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("child wait failed")
    monkeypatch.setattr(gate, "run_logged", broken)
    result = gate.collect(output, profile="change-lifecycle")
    assert result["status"] == "failed"
    assert any(name.endswith("change-lifecycle-report.json") for name in result["raw_files"])
