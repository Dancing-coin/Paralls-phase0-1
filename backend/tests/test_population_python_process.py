"""原采集进程 PID 与实际 Python/依赖环境必须一致。"""
import json
import os
from pathlib import Path
import subprocess
import sys


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
