from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common
import harness
from run_context import run_scope


def fixture_project(tmp_path, code, *, result=True):
    project = tmp_path / 'project'
    scripts = project / 'scripts'
    scripts.mkdir(parents=True)
    (scripts / 'probe.py').write_text(code, encoding='utf-8')
    configs = project / '.harness' / 'profiles'
    configs.mkdir(parents=True)
    config = {'schema_version': 1, 'name': 'probe', 'script': 'scripts/probe.py', 'timeout_seconds': 5}
    if result:
        config.update(result_artifact='.harness/verification/result.json', success_key='passed')
    (configs / 'probe.json').write_text(json.dumps(config), encoding='utf-8')
    subprocess.run(['git', 'init', '-q', str(project)], check=True)
    subprocess.run(['git', '-C', str(project), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(project), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'fixture'], check=True)
    return project


def invoke(monkeypatch, project, export):
    monkeypatch.setattr(harness, 'repo_root', lambda: project)
    monkeypatch.setattr(sys, 'argv', ['harness', '--profile', 'probe', '--export-evidence', str(export)])
    return harness.main()


def test_missing_report_cannot_reuse_source_tree_success(tmp_path, monkeypatch):
    project = fixture_project(tmp_path, 'print("no report")')
    stale = project / '.harness/verification/result.json'
    stale.parent.mkdir()
    stale.write_text('{"passed": true}')
    result = invoke(monkeypatch, project, tmp_path / 'export')
    assert result != 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['failure_kind'] == 'evidence'
    assert stale.exists()


@pytest.mark.parametrize(('passed', 'exit_code'), [(True, 2), (False, 0)])
def test_exit_code_and_declared_result_must_both_pass(tmp_path, monkeypatch, passed, exit_code):
    code = ("import os,json,pathlib\n"
            "root=pathlib.Path(os.environ['HARNESS_ATTEMPT_ROOT'])\n"
            f"(root/'result.json').write_text(json.dumps({{'passed': {passed!r}}}))\n"
            f"raise SystemExit({exit_code})\n")
    project = fixture_project(tmp_path, code)
    assert invoke(monkeypatch, project, tmp_path / 'export') != 0


def test_success_report_is_bound_to_run_and_cleanup(tmp_path, monkeypatch):
    code = "import os,pathlib\n(pathlib.Path(os.environ['HARNESS_ATTEMPT_ROOT'])/'result.json').write_text('{\"passed\": true}')"
    project = fixture_project(tmp_path, code)
    assert invoke(monkeypatch, project, tmp_path / 'export') == 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['status'] == 'passed'
    assert report['profiles'][0]['run_id'] == report['run_id']
    assert report['cleanup_status'] == 'passed'
    assert not (project / '.harness/verification').exists()


def test_revision_changes_when_same_dirty_file_changes(tmp_path):
    project = fixture_project(tmp_path, 'print(1)', result=False)
    source = project / 'scripts/probe.py'
    source.write_text('print(2)')
    first = common.evidence_revision(project)
    source.write_text('print(3)')
    assert common.evidence_revision(project) != first


def test_streamed_output_is_bounded(tmp_path):
    result = common.run_command([sys.executable, '-c', 'print("x" * 100000)'], tmp_path,
                                tmp_path / 'log', timeout_seconds=5, max_output_bytes=2048)
    assert result.returncode == 0
    assert len(result.stdout.encode()) < 2300
    assert (tmp_path / 'log').stat().st_size < 2300
    assert 'truncated' in result.stdout


def test_missing_godot_is_blocked_without_executing_profile(tmp_path, monkeypatch):
    project = fixture_project(tmp_path, 'raise AssertionError("must not run")', result=False)
    config_path = project / '.harness/profiles/probe.json'
    config = json.loads(config_path.read_text())
    config['requires_godot'] = True
    config_path.write_text(json.dumps(config))
    monkeypatch.delenv('GODOT_EXE', raising=False)
    assert invoke(monkeypatch, project, tmp_path / 'export') != 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['status'] == 'blocked'
    assert report['profiles'][0]['attempts'] == 0


def test_explicit_process_retry_uses_a_fresh_attempt(tmp_path, monkeypatch):
    code = "import os\nraise SystemExit(75 if os.environ['HARNESS_ATTEMPT_ID'].endswith(':1') else 0)"
    project = fixture_project(tmp_path, code, result=False)
    path = project / '.harness/profiles/probe.json'
    config = json.loads(path.read_text())
    config.update(max_attempts=2, retry_exit_codes=[75])
    path.write_text(json.dumps(config))
    assert invoke(monkeypatch, project, tmp_path / 'export') == 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['attempts'] == 2
    assert (tmp_path / 'export/profiles/probe/1/command.log').exists()
    assert (tmp_path / 'export/profiles/probe/2/command.log').exists()


def test_source_change_invalidates_success(tmp_path, monkeypatch):
    project = fixture_project(tmp_path, "from pathlib import Path\nPath('scripts/probe.py').write_text('print(2)')", result=False)
    assert invoke(monkeypatch, project, tmp_path / 'export') != 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['failure_kind'] == 'evidence'


def test_assertion_failure_with_retry_exit_code_is_not_retried(tmp_path, monkeypatch):
    code = ("import os,json,pathlib\n"
            "pathlib.Path(os.environ['HARNESS_ATTEMPT_ROOT']).joinpath('result.json').write_text('{\"passed\": false}')\n"
            "raise SystemExit(75)\n")
    project = fixture_project(tmp_path, code)
    path = project / '.harness/profiles/probe.json'
    config = json.loads(path.read_text())
    config.update(max_attempts=2, retry_exit_codes=[75])
    path.write_text(json.dumps(config))
    assert invoke(monkeypatch, project, tmp_path / 'export') != 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['attempts'] == 1
    assert report['profiles'][0]['failure_kind'] == 'assertion'


def test_cancelled_run_exports_cancelled_summary(tmp_path, monkeypatch):
    project = fixture_project(tmp_path, 'print(1)', result=False)
    monkeypatch.setattr(harness, '_execute_profile', lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert invoke(monkeypatch, project, tmp_path / 'export') == 130
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['status'] == 'cancelled'
    assert report['profiles'][0]['failure_kind'] == 'cancelled'
    assert report['profiles'][0]['revision'] == report['revision']


def test_cancelled_run_keeps_interrupted_profile_in_pending_list(tmp_path, monkeypatch):
    project = fixture_project(tmp_path, 'print(1)', result=False)
    registry = SimpleNamespace(profiles={'first': {}, 'second': {}})
    monkeypatch.setattr(harness, 'repo_root', lambda: project)
    monkeypatch.setattr(harness, 'load_profile_registry', lambda _root: registry)
    monkeypatch.setattr(harness, 'select_profiles', lambda *_args, **_kwargs: ['first', 'second'])
    monkeypatch.setattr(sys, 'argv', ['harness', '--profile', 'all', '--export-evidence', str(tmp_path / 'export')])

    def execute(_root, _run, profile, *_args):
        if profile == 'first':
            return {'profile': profile, 'status': 'passed', 'failure_kind': None, 'exit_code': 0}
        raise KeyboardInterrupt()

    monkeypatch.setattr(harness, '_execute_profile', execute)
    assert harness.main() == 130
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['not_executed'] == ['second']
    assert report['profiles'][-1]['revision'] == report['revision']


def test_process_cleanup_failure_is_classified_separately(tmp_path, monkeypatch):
    project = fixture_project(tmp_path, 'print(1)', result=False)
    monkeypatch.setattr(harness, 'run_command', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('child cleanup boom')))
    assert invoke(monkeypatch, project, tmp_path / 'export') != 0
    report = json.loads((tmp_path / 'export/harness-run-report.json').read_text())
    assert report['profiles'][0]['failure_kind'] == 'cleanup'
    assert report['profiles'][0]['status'] == 'failed'
