import os
from pathlib import Path
import subprocess
import sys


def test_storage_lease_blocks_an_idle_writer_and_survives_process_exit(tmp_path: Path):
    from app.world_runtime.storage_lease import RuntimeStorageLease

    database = tmp_path / "graph.db"
    code = """
import os, sys
from app.world_runtime.storage_lease import RuntimeStorageLease
try:
    lease = RuntimeStorageLease(sys.argv[1])
except RuntimeError as error:
    assert str(error).startswith('runtime_storage_in_use:')
    raise SystemExit(2)
os._exit(0)
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    with RuntimeStorageLease(database):
        # 没有SQLite写事务的空闲服务也必须阻止离线维护。
        child = subprocess.run([sys.executable, "-c", code, str(database)], env=env, capture_output=True, timeout=15)
        assert child.returncode == 2, child.stderr
    child = subprocess.run([sys.executable, "-c", code, str(database)], env=env, capture_output=True, timeout=15)
    assert child.returncode == 0, child.stderr
    # 强制退出由OS释放锁，不按PID猜测，更不删除锁文件来抢占。
    with RuntimeStorageLease(database):
        pass
