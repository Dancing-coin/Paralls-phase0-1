"""采集器启动实际 Python 进程，避免 Windows venv launcher 的额外 PID。"""
import os
import site
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
        if not site.ENABLE_USER_SITE:
            # base interpreter 不继承父 venv 的 site 禁用状态，必须显式传递。
            env['PYTHONNOUSERSITE'] = '1'
        if site.ENABLE_USER_SITE and not env.get('PYTHONNOUSERSITE'):
            paths.append(site.getusersitepackages())
        env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(path for path in paths if path))
    return [executable, *map(str, arguments)], env
