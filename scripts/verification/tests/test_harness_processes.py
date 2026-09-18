from __future__ import annotations

import ctypes
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common
from run_context import run_scope


def _is_running(pid: int) -> bool:
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    status = Path(f"/proc/{pid}/stat")
    return not status.exists() or status.read_text().split()[2] != "Z"


def _cleanup_test_processes(pids: list[int]) -> None:
    for pid in pids:
        if not _is_running(pid):
            continue
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        else:
            os.kill(pid, signal.SIGKILL)


@pytest.mark.parametrize("parent_hangs", [False, True])
def test_command_reclaims_child_and_grandchild_even_after_parent_exit(tmp_path: Path, parent_hangs: bool) -> None:
    pid_path = tmp_path / "pids.json"
    child_code = (
        "import os,subprocess,sys,time,json,pathlib\n"
        "leaf=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\n"
        f"pathlib.Path({str(pid_path)!r}).write_text(json.dumps([os.getpid(),leaf.pid]))\n"
        "time.sleep(30)\n"
    )
    parent_code = (
        "import subprocess,sys,time,pathlib\n"
        f"subprocess.Popen([sys.executable,'-c',{child_code!r}])\n"
        f"while not pathlib.Path({str(pid_path)!r}).exists(): time.sleep(.01)\n"
        + ("time.sleep(30)\n" if parent_hangs else "")
    )
    pids: list[int] = []
    try:
        result = common.run_command([sys.executable, "-c", parent_code], tmp_path, tmp_path / "tree.log", timeout_seconds=2)
        pids = json.loads(pid_path.read_text())
        assert result.returncode == (124 if parent_hangs else 0)
        assert not any(_is_running(pid) for pid in pids), "命令结束后遗留了本轮子进程"
    finally:
        if not pids and pid_path.exists():
            pids = json.loads(pid_path.read_text())
        _cleanup_test_processes(pids)


def test_huge_unbroken_output_is_bounded_in_memory_and_log(tmp_path: Path) -> None:
    result = common.run_command(
        [sys.executable, "-c", "import os;os.write(1,b'x'*2000000)"], tmp_path, tmp_path / "output.log",
        timeout_seconds=5, max_output_bytes=1024,
    )
    assert result.returncode == 0
    assert result.output_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 1024
    assert (tmp_path / "output.log").stat().st_size <= 1024
    assert "truncated" in result.stdout


def test_marker_after_truncation_and_across_chunks_is_still_matched(tmp_path: Path) -> None:
    code = "import os,time;os.write(1,b'x'*32766+b'MARK');time.sleep(.05);os.write(1,b'ER_OK');time.sleep(30)"
    result = common.run_command_until_markers(
        [sys.executable, "-c", code], tmp_path, tmp_path / "marker.log",
        success_markers=["MARKER_OK"], timeout_seconds=3, max_output_bytes=1024,
    )
    assert result.returncode == 0
    assert result.marker_found is True
    assert result.output_truncated is True
    assert len(result.stdout.encode("utf-8")) <= 1024
    assert (tmp_path / "marker.log").stat().st_size <= 1024


def test_successful_exit_without_required_marker_is_failure(tmp_path: Path) -> None:
    result = common.run_command_until_markers(
        [sys.executable, "-c", "print('incomplete')"], tmp_path, tmp_path / "no-marker.log",
        success_markers=["MUST_APPEAR"], timeout_seconds=3,
    )
    assert result.marker_found is False
    assert result.returncode != 0


def test_existing_backend_is_reused_or_blocked_without_termination(monkeypatch, tmp_path: Path) -> None:
    health = {"status": "ok", "worktree_root": str(tmp_path)}
    monkeypatch.setattr(common, "get_health", lambda: health)
    def unexpected_termination(*args, **kwargs):
        pytest.fail("不得终止不属于本次运行的 backend")
    monkeypatch.setattr(common, "_terminate_listener_pid", unexpected_termination)
    monkeypatch.setattr(common, "_find_listener_pid", lambda port: 4242)

    assert common.ensure_backend(tmp_path, sys.executable) == (health, None)
    with pytest.raises(RuntimeError, match="owned|external|occupied"):
        common.ensure_backend(tmp_path, sys.executable, prefer_fresh_backend=True)


def test_stop_backend_preserves_reused_backend() -> None:
    common.stop_backend(None)


def test_owned_backend_stop_reclaims_descendants_and_closes_logs(monkeypatch, tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    backend.mkdir()
    pid_path = tmp_path / "backend-child.txt"
    (backend / "uvicorn.py").write_text(
        "import subprocess,sys,time,pathlib\n"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])\n"
        f"pathlib.Path({str(pid_path)!r}).write_text(str(child.pid))\n"
        "print('backend started',flush=True)\n"
        "time.sleep(30)\n", encoding="utf-8",
    )
    monkeypatch.setattr(common, "get_health", lambda: {"worktree_root": str(tmp_path)} if pid_path.exists() else None)
    monkeypatch.setattr(common, "_find_listener_pid", lambda port: None)
    process = None
    try:
        with run_scope(tmp_path) as context:
            _, process = common.ensure_backend(tmp_path, sys.executable)
            common.stop_backend(process)
            assert process.poll() is not None
            assert not _is_running(int(pid_path.read_text()))
            for path in context.evidence_root.glob("backend-verify.*.log"):
                path.unlink()
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if pid_path.exists():
            _cleanup_test_processes([int(pid_path.read_text())])
