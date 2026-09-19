"""采集器启动实际 Python 进程，避免 Windows venv launcher 的额外 PID。"""
import os
import sys
import sysconfig


def python_process(arguments, environment):
    env = dict(environment)
    executable = sys.executable
    if os.name == 'nt':
        executable = sys._base_executable
        # base executable 不经过 venv launcher；保留当前环境的真实依赖目录。
        paths = [env.get('PYTHONPATH', '')]
        paths.extend(sysconfig.get_path(name) for name in ('purelib', 'platlib'))
        env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(path for path in paths if path))
    return [executable, *map(str, arguments)], env
