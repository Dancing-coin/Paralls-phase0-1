from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def context_module():
    assert importlib.util.find_spec('run_context') is not None, '缺少统一运行上下文'
    return importlib.import_module('run_context')


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    for key in ('HARNESS_RUN_ID', 'HARNESS_PROJECT_ROOT', 'HARNESS_EVIDENCE_ROOT',
                'HARNESS_ATTEMPT_ROOT', 'HARNESS_ATTEMPT_ID'):
        monkeypatch.delenv(key, raising=False)


def test_nested_scope_keeps_evidence_until_outer_exit(tmp_path):
    module = context_module()
    with module.run_scope(tmp_path) as outer:
        report = outer.evidence_root / 'report.json'
        report.write_text('{}', encoding='utf-8')
        with module.run_scope(tmp_path) as inner:
            assert inner.evidence_root == outer.evidence_root
        assert report.exists()
    assert not outer.evidence_root.exists()
    assert 'HARNESS_RUN_ID' not in os.environ


def test_failure_cleans_owned_directory_and_keeps_unrelated_file(tmp_path):
    module = context_module()
    unrelated = tmp_path / 'keep.txt'
    unrelated.write_text('用户文件', encoding='utf-8')
    with pytest.raises(ValueError, match='断言失败'):
        with module.run_scope(tmp_path) as run:
            (run.evidence_root / 'log.txt').write_text('diagnostic')
            raise ValueError('断言失败')
    assert not run.evidence_root.exists()
    assert unrelated.read_text(encoding='utf-8') == '用户文件'


def test_explicit_export_survives_cleanup(tmp_path):
    module = context_module()
    project = tmp_path / 'project'
    project.mkdir()
    export = tmp_path / 'export'
    with module.run_scope(project, export_to=export) as run:
        (run.evidence_root / 'report.json').write_text('{}')
    assert (export / 'report.json').read_text() == '{}'
    assert not run.evidence_root.exists()


def test_export_rejects_source_tree_and_nonempty_directory(tmp_path):
    module = context_module()
    project = tmp_path / 'project'
    project.mkdir()
    outside = tmp_path / 'existing'
    outside.mkdir()
    (outside / 'keep').write_text('keep')
    for destination in (project, project / 'evidence', outside):
        with pytest.raises(ValueError):
            with module.run_scope(project, export_to=destination):
                pytest.fail('危险导出路径被接受')
    assert (outside / 'keep').read_text() == 'keep'


def test_inherited_unowned_root_is_rejected(tmp_path, monkeypatch):
    module = context_module()
    monkeypatch.setenv('HARNESS_EVIDENCE_ROOT', str(tmp_path))
    monkeypatch.setenv('HARNESS_PROJECT_ROOT', str(tmp_path))
    monkeypatch.setenv('HARNESS_RUN_ID', 'forged')
    with pytest.raises(RuntimeError, match='所有权'):
        with module.run_scope(tmp_path):
            pytest.fail('伪造运行目录被接受')


def test_attempts_do_not_reuse_previous_report(tmp_path):
    module = context_module()
    with module.run_scope(tmp_path) as run:
        with module.attempt_scope(run, 'docs', 1) as first:
            (first / 'report.json').write_text('{}')
        with module.attempt_scope(run, 'docs', 2) as second:
            assert not (second / 'report.json').exists()
            assert first != second
        assert (first / 'report.json').exists()


def test_sibling_dependencies_use_explicit_current_run_index(tmp_path):
    import json
    from common import artifact_path
    module = context_module()
    with module.run_scope(tmp_path) as run:
        with module.attempt_scope(run, 'first', 1) as first:
            (first / 'first.json').write_text('{}')
        (run.evidence_root / '.harness-artifacts.json').write_text(json.dumps({
            'run_id': run.run_id, 'artifacts': {'first.json': 'profiles/first/1/first.json'}}))
        with module.attempt_scope(run, 'second', 1):
            assert artifact_path(tmp_path, '.harness/verification/first.json').read_text() == '{}'


def test_sibling_artifact_reference_round_trip(tmp_path):
    from common import artifact_path, artifact_ref
    module = context_module()
    with module.run_scope(tmp_path) as run:
        with module.attempt_scope(run, 'first', 1) as first:
            report = first / 'first.json'
            report.write_text('{}')
        with module.attempt_scope(run, 'second', 1):
            assert artifact_path(tmp_path, artifact_ref(tmp_path, report)) == report


def test_export_never_overwrites_a_file_created_during_run(tmp_path):
    module = context_module()
    project = tmp_path / 'project'
    project.mkdir()
    export = tmp_path / 'export'
    with pytest.raises(RuntimeError):
        with module.run_scope(project, export_to=export) as run:
            (run.evidence_root / 'report.json').write_text('ours')
            export.mkdir()
            (export / 'report.json').write_text('theirs')
    assert (export / 'report.json').read_text() == 'theirs'
    assert not run.evidence_root.exists()


def test_body_error_is_preserved_when_cleanup_fails(tmp_path, monkeypatch):
    import run_context
    original = run_context.shutil.rmtree
    monkeypatch.setattr(run_context.shutil, 'rmtree', lambda path: (_ for _ in ()).throw(OSError('cleanup boom')))
    with pytest.raises(ValueError, match='original') as error:
        with run_context.run_scope(tmp_path):
            raise ValueError('original')
    assert any('cleanup boom' in note for note in error.value.__notes__)
    monkeypatch.setattr(run_context.shutil, 'rmtree', original)
