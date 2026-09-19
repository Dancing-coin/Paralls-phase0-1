"""服务和离线维护共同持有的存档进程锁。"""
from pathlib import Path
import sys


class RuntimeStorageLease:
    def __init__(self, database_path: str | Path) -> None:
        database = Path(database_path).resolve()
        self.path = database.with_name(f"{database.name}.runtime.lock")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+b")
        try:
            if self._stream.seek(0, 2) == 0:
                self._stream.write(b"\0")
                self._stream.flush()
            self._stream.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self._stream.close()
            raise RuntimeError(f"runtime_storage_in_use:{self.path}") from error

    def close(self) -> None:
        # 不删除锁文件：删除会让另一进程锁住不同inode，从而产生双writer。
        if not self._stream.closed:
            self._stream.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            self._stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
