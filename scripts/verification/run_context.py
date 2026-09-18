from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


MARKER = '.harness-owner.json'
ENV_KEYS = ('HARNESS_RUN_ID', 'HARNESS_PROJECT_ROOT', 'HARNESS_EVIDENCE_ROOT',
            'HARNESS_ATTEMPT_ROOT', 'HARNESS_ATTEMPT_ID', 'PYTHONDONTWRITEBYTECODE',
            'PARALLS_HEAVENLY_GRAPH_PATH')


@dataclass(frozen=True)
class RunContext:
    run_id: str
    project_root: Path
    evidence_root: Path
    owns_root: bool


def _linked(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def _validate_owner(root: Path, project: Path, run_id: str) -> None:
    try:
        marker = json.loads((root / MARKER).read_text(encoding='utf-8'))
        valid = (not _linked(root) and marker == {'run_id': run_id, 'project_root': str(project)}
                 and root.name == 'paralls-harness-' + run_id
                 and not root.is_relative_to(project))
    except (OSError, ValueError):
        valid = False
    if not valid:
        raise RuntimeError(f'Harness 运行目录所有权无效: {root}')


def current_run(project_root: Path) -> RunContext:
    project = project_root.resolve()
    if os.environ.get('HARNESS_PROJECT_ROOT') != str(project):
        raise RuntimeError(f'缺少当前项目的 Harness run_scope: {project}')
    root_text = os.environ.get('HARNESS_EVIDENCE_ROOT')
    run_id = os.environ.get('HARNESS_RUN_ID', '')
    if not root_text or not run_id:
        raise RuntimeError('缺少 Harness 运行上下文')
    root = Path(root_text).absolute()
    _validate_owner(root, project, run_id)
    return RunContext(run_id, project, root, False)


def output_root(project_root: Path) -> Path:
    run = current_run(project_root)
    attempt = os.environ.get('HARNESS_ATTEMPT_ROOT')
    if not attempt:
        return run.evidence_root
    path = Path(attempt).resolve()
    if not path.is_relative_to(run.evidence_root) or path == run.evidence_root:
        raise RuntimeError('Harness attempt 目录越界')
    return path


def _export_destination(project: Path, destination: Path | None) -> Path | None:
    if destination is None:
        return None
    raw = destination.absolute()
    if any(_linked(part) for part in (raw, *raw.parents)):
        raise ValueError('证据导出路径不能包含链接')
    path = raw.resolve()
    if path.is_relative_to(project) or project.is_relative_to(path):
        raise ValueError('证据必须导出到仓库外的独立目录')
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError('证据导出目录必须不存在或为空')
    return path


@contextmanager
def run_scope(project_root: Path, *, export_to: Path | None = None) -> Iterator[RunContext]:
    project = project_root.resolve()
    if os.environ.get('HARNESS_PROJECT_ROOT') == str(project):
        if export_to is not None:
            raise ValueError('只有顶层运行可以导出证据')
        yield current_run(project)
        return
    policy_path = project / '.harness' / 'retention-policy.json'
    if policy_path.exists():
        policy = json.loads(policy_path.read_text(encoding='utf-8'))
        expected = {'schema_version': 2, 'generated_evidence_root': 'system-temp',
                    'default_action': 'delete', 'export_mode': 'explicit-export',
                    'export_requires_external_directory': True}
        if any(policy.get(key) != value for key, value in expected.items()):
            raise ValueError('Harness retention policy 与临时证据契约不一致')
    destination = _export_destination(project, export_to)
    saved = {key: os.environ.get(key) for key in ENV_KEYS}
    run_id = uuid.uuid4().hex
    root = Path(tempfile.gettempdir()).resolve() / ('paralls-harness-' + run_id)
    root.mkdir()
    (root / MARKER).write_text(json.dumps({'run_id': run_id, 'project_root': str(project)}), encoding='utf-8')
    run = RunContext(run_id, project, root, True)
    os.environ.update(HARNESS_RUN_ID=run_id, HARNESS_PROJECT_ROOT=str(project),
                      HARNESS_EVIDENCE_ROOT=str(root), PYTHONDONTWRITEBYTECODE='1',
                      PARALLS_HEAVENLY_GRAPH_PATH=str(root / 'runtime.sqlite3'))
    os.environ.pop('HARNESS_ATTEMPT_ROOT', None)
    os.environ.pop('HARNESS_ATTEMPT_ID', None)
    try:
        yield run
    finally:
        body_error = __import__('sys').exc_info()[1]
        errors: list[str] = []
        exported = False
        try:
            _validate_owner(root, project, run_id)
            # 不跟随运行期间创建的目录链接导出外部数据。
            if destination is not None:
                _export_destination(project, destination)
                if any(_linked(path) for path in root.rglob('*')):
                    raise RuntimeError('运行证据包含链接，拒绝导出')
                destination.mkdir(parents=True, exist_ok=True)
                # 排他创建每个文件，即使并行写入也不能覆盖已有内容。
                for source in root.rglob('*'):
                    target = destination / source.relative_to(root)
                    if source.is_dir():
                        target.mkdir(exist_ok=True)
                    else:
                        with source.open('rb') as input_file, target.open('xb') as output_file:
                            shutil.copyfileobj(input_file, output_file)
                exported = True
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f'export: {exc}')
        try:
            _validate_owner(root, project, run_id)
            # Python rmtree 不递归跟随 symlink 或 Windows junction。
            shutil.rmtree(root)
        except (OSError, RuntimeError) as exc:
            errors.append(f'cleanup: {exc}; remaining={root}')
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        status = 'failed' if errors else 'passed'
        if exported and destination is not None:
            for name in ('harness-run-report.json', 'run-manifest.json'):
                path = destination / name
                if path.is_file():
                    try:
                        payload = json.loads(path.read_text(encoding='utf-8'))
                        payload['cleanup_status'] = status
                        if errors:
                            payload['overall_harness_passed'] = False
                            payload['cleanup_errors'] = errors
                        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
                    except (OSError, ValueError) as exc:
                        errors.append(f'finalize export: {exc}')
        print(f'harness_cleanup={status} run_id={run_id}')
        if errors:
            cleanup_error = RuntimeError('; '.join(errors))
            if body_error is not None:
                body_error.add_note(f'Harness cleanup failed: {cleanup_error}')
            else:
                raise cleanup_error


@contextmanager
def attempt_scope(run: RunContext, profile: str, attempt: int) -> Iterator[Path]:
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', profile) or attempt < 1:
        raise ValueError('无效的 profile/attempt')
    root = output_root(run.project_root) / 'profiles' / profile / str(attempt)
    root.mkdir(parents=True, exist_ok=False)
    keys = ('HARNESS_ATTEMPT_ROOT', 'HARNESS_ATTEMPT_ID')
    saved = {key: os.environ.get(key) for key in keys}
    os.environ['HARNESS_ATTEMPT_ROOT'] = str(root)
    os.environ['HARNESS_ATTEMPT_ID'] = f'{profile}:{attempt}'
    try:
        yield root
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
