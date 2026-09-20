"""冷检出必须携带脚本 UID，避免首次导入改变验收源码身份。"""
from pathlib import Path
import re
import subprocess


def test_tracked_gdscript_and_shader_uids_are_present_in_checkout():
    root = Path(__file__).resolve().parents[3]
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0'))
    scripts = sorted(path for path in tracked if path.endswith(('.gd', '.gdshader')))
    assert scripts
    missing = [path + '.uid' for path in scripts if path + '.uid' not in tracked]
    assert not missing, f'Godot 首次导入会生成未跟踪 UID: {missing}'
    for path in scripts:
        assert re.fullmatch(r'uid://[a-z0-9]+', (root / (path + '.uid')).read_text(encoding='utf-8').strip()), path
