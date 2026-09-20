"""原采集进程 PID 与实际 Python/依赖环境必须一致。"""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


def test_python_process_pid_is_actual_interpreter_and_preserves_dependencies():
    import fastapi
    from scripts.verification.population_python_process import python_process
    command, environment = python_process(['-c',
        'import os,json,fastapi; print(json.dumps(dict(pid=os.getpid(),dependency=fastapi.__file__)))'], os.environ)
    child = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output, error = child.communicate(timeout=15)
    assert child.returncode == 0, error
    observed = json.loads(output)
    assert observed['pid'] == child.pid
    assert Path(observed['dependency']).resolve() == Path(fastapi.__file__).resolve()
    if os.name == 'nt':
        assert Path(command[0]).resolve() == Path(sys._base_executable).resolve()

def test_non_windows_preserves_venv_symlink_executable(monkeypatch):
    from scripts.verification import population_python_process as launch
    monkeypatch.setattr(launch.os, 'name', 'posix')
    monkeypatch.setattr(launch.sys, 'executable', '/workspace/venv/bin/python')
    command, environment = launch.python_process(['script.py'], {'PYTHONPATH': 'backend'})
    assert command[0] == '/workspace/venv/bin/python'
    assert environment == {'PYTHONPATH': 'backend'}


@pytest.mark.parametrize('user_enabled,child_disabled', [(True, False), (False, False), (True, True)])
def test_windows_child_keeps_venv_priority_and_respects_disabled_user_site(tmp_path, monkeypatch, user_enabled, child_disabled):
    from scripts.verification import population_python_process as launch
    venv_site = tmp_path / 'venv-site'
    user_site = tmp_path / 'user-site'
    for directory, value in [(venv_site, 'venv'), (user_site, 'user')]:
        directory.mkdir()
        (directory / 'dependency_priority_probe.py').write_text(f'origin = {value!r}', encoding='utf-8')
    monkeypatch.setattr(launch, 'os', SimpleNamespace(name='nt', pathsep=os.pathsep))
    monkeypatch.setattr(launch.site, 'ENABLE_USER_SITE', user_enabled)
    monkeypatch.setattr(launch.site, 'getusersitepackages', lambda: str(user_site))
    monkeypatch.setattr(launch.sysconfig, 'get_path', lambda _: str(venv_site))
    original = dict(os.environ, PYTHONPATH='')
    original.pop('PYTHONNOUSERSITE', None)
    if child_disabled:
        original['PYTHONNOUSERSITE'] = '1'
    before = dict(original)
    command, environment = launch.python_process(['-c',
        'import json,site,dependency_priority_probe as p; print(json.dumps([p.origin,site.ENABLE_USER_SITE]))'], original)
    child = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=15)
    assert child.returncode == 0, child.stderr
    origin, child_user_enabled = json.loads(child.stdout)
    assert origin == 'venv'
    if not user_enabled or child_disabled:
        assert child_user_enabled is False
    assert (str(user_site) in environment['PYTHONPATH'].split(os.pathsep)) == (user_enabled and not child_disabled)
    assert environment['PYTHONPATH'].split(os.pathsep).count(str(venv_site)) == 1
    assert original == before
