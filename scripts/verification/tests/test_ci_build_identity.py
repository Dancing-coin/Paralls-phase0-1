"""构建产物不能把同一提交的正式证据误标为源码变更。"""
from pathlib import Path
import subprocess

from scripts.verification.common import evidence_revision


def test_backend_wheel_build_is_ignored_but_real_source_changes_still_change_identity(tmp_path):
    root = Path(__file__).resolve().parents[3]
    (tmp_path / '.gitignore').write_bytes((root / '.gitignore').read_bytes())
    source = tmp_path / 'backend/app/main.py'
    source.parent.mkdir(parents=True)
    source.write_text('VALUE = 1\n', encoding='utf-8')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path, text=True).strip()
    git('init', '--quiet')
    git('add', '.')
    git('-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '--quiet', '-m', 'fixture')
    head = git('rev-parse', 'HEAD')
    built = tmp_path / 'backend/build/lib/app/main.py'
    built.parent.mkdir(parents=True)
    built.write_bytes(source.read_bytes())
    assert evidence_revision(tmp_path) == head
    source.write_text('VALUE = 2\n', encoding='utf-8')
    assert evidence_revision(tmp_path).startswith(head + '+dirty:')
