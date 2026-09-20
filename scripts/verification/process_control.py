from __future__ import annotations

import ctypes
import math
import os
import signal
import subprocess
import threading
import time
from ctypes import wintypes
from pathlib import Path


class _WindowsJob:
    def __init__(self) -> None:
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            "SetInformationJobObject": ([wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            "AssignProcessToJobObject": ([wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            "TerminateJobObject": ([wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "CreateToolhelp32Snapshot": ([wintypes.DWORD, wintypes.DWORD], wintypes.HANDLE),
            "Thread32First": ([wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL),
            "Thread32Next": ([wintypes.HANDLE, ctypes.c_void_p], wintypes.BOOL),
            "OpenThread": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "ResumeThread": ([wintypes.HANDLE], wintypes.DWORD),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.kernel, name)
            function.argtypes = arguments
            function.restype = result
        self.handle = self.kernel.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.WinError(ctypes.get_last_error())
            self.close()
            raise error

    def attach_and_resume(self, process: subprocess.Popen) -> None:
        if not self.kernel.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = self.kernel.CreateToolhelp32Snapshot(4, 0)  # TH32CS_SNAPTHREAD
        if snapshot == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = _ThreadEntry()
            entry.dwSize = ctypes.sizeof(entry)
            found = self.kernel.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.th32OwnerProcessID == process.pid:
                    thread = self.kernel.OpenThread(2, False, entry.th32ThreadID)  # THREAD_SUSPEND_RESUME
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if self.kernel.ResumeThread(thread) == 0xFFFFFFFF:
                            raise ctypes.WinError(ctypes.get_last_error())
                        return
                    finally:
                        self.kernel.CloseHandle(thread)
                found = self.kernel.Thread32Next(snapshot, ctypes.byref(entry))
            raise RuntimeError(f"Cannot resume owned process {process.pid}: initial thread not found")
        finally:
            self.kernel.CloseHandle(snapshot)

    def terminate_and_wait(self) -> None:
        if not self.kernel.TerminateJobObject(self.handle, 1):
            raise ctypes.WinError(ctypes.get_last_error())
        # 活动计数可先于子进程I/O资源释放归零；等待Job退出信号后才允许清理存档。
        result = self.kernel.WaitForSingleObject(self.handle, 5000)
        if result == 0:  # WAIT_OBJECT_0
            return
        if result == 0xFFFFFFFF:  # WAIT_FAILED
            raise ctypes.WinError(ctypes.get_last_error())
        raise RuntimeError(f"Owned Windows job exit was not confirmed: wait status {result}")

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self.kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimits), ("IoInfo", ctypes.c_ulonglong * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ThreadID", wintypes.DWORD),
        ("th32OwnerProcessID", wintypes.DWORD), ("tpBasePri", wintypes.LONG),
        ("tpDeltaPri", wintypes.LONG), ("dwFlags", wintypes.DWORD),
    ]


class OwnedProcess:
    """只回收本对象创建的进程组；不通过端口推断进程所有权。"""

    def __init__(self, args: list[str], **kwargs) -> None:
        self.job = _WindowsJob() if os.name == "nt" else None
        self.closed = False
        if self.job is not None:
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | 4  # CREATE_SUSPENDED
        else:
            kwargs["start_new_session"] = True
        self.process: subprocess.Popen | None = None
        try:
            self.process = subprocess.Popen(args, **kwargs)
            if self.job is not None:
                self.job.attach_and_resume(self.process)
            self.process._harness_owner = self
        except BaseException as original:
            try:
                if self.process is not None:
                    self.process.kill()
                    self.process.wait(timeout=5)
                if self.job is not None:
                    self.job.close()
            except BaseException as cleanup_error:
                original.add_note(f"Process startup cleanup failed: {cleanup_error}")
            raise

    def close(self) -> None:
        if self.closed:
            return
        try:
            if self.job is not None:
                self.job.terminate_and_wait()
            else:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            self.process.wait(timeout=5)
            if self.job is None:
                _wait_for_process_group_exit(self.process.pid)
        finally:
            if self.job is not None:
                self.job.close()
            self.closed = True

    def __enter__(self) -> OwnedProcess:
        return self

    def __exit__(self, _kind, original, _traceback) -> None:
        try:
            self.close()
        except BaseException as cleanup_error:
            if original is None:
                raise
            original.add_note(f"Owned process cleanup failed: {cleanup_error}")


def _wait_for_process_group_exit(group_id: int) -> None:
    deadline = time.monotonic() + 5
    while True:
        try:
            os.killpg(group_id, 0)
        except ProcessLookupError:
            return
        proc_root = Path("/proc")
        if proc_root.is_dir():
            active = False
            for entry in proc_root.iterdir():
                if not entry.name.isdecimal():
                    continue
                try:
                    fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                except (OSError, IndexError):
                    continue
                if fields[2] == str(group_id) and fields[0] != "Z":
                    active = True
                    break
            # 已终止但等待 init 回收的僵尸不持有运行资源。
            if not active:
                return
        if time.monotonic() >= deadline:
            raise RuntimeError(f"Owned process group {group_id} is still active after cleanup")
        time.sleep(0.01)


class BoundedOutput:
    """分块读取并实时写入有界日志，marker 在丢弃输出前匹配。"""

    def __init__(self, stream, path: Path, limit: int, markers: list[str] | None = None, require_all: bool = False) -> None:
        self.stream = stream
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open("w+b")
        self.limit = limit
        self.data = bytearray()
        self.truncated = False
        self.error: BaseException | None = None
        self.marker_found = threading.Event()
        self.markers = [marker.encode("utf-8") for marker in (markers or [])]
        self.require_all = require_all
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        tail = b""
        found: set[bytes] = set()
        overlap = max((len(marker) - 1 for marker in self.markers), default=0)
        try:
            while chunk := self.stream.read(16384):
                if self.markers:
                    candidate = tail + chunk
                    found.update(marker for marker in self.markers if marker in candidate)
                    if (self.require_all and len(found) == len(set(self.markers))) or (not self.require_all and found):
                        self.marker_found.set()
                    tail = candidate[-overlap:] if overlap else b""
                retained = chunk[:max(0, self.limit - len(self.data))]
                self.data.extend(retained)
                if len(retained) < len(chunk):
                    self.truncated = True
                if retained:
                    self.handle.write(retained)
                    self.handle.flush()
        except BaseException as error:
            self.error = error
        finally:
            self.stream.close()

    def finish(self, notice: str = "") -> str:
        self.thread.join(timeout=5)
        try:
            if self.thread.is_alive():
                raise RuntimeError("Owned process output reader did not stop during cleanup")
            if self.error is not None:
                raise RuntimeError(f"Failed to capture process output: {self.error}") from self.error
            footer = (("\n[harness] output truncated\n" if self.truncated else "") + notice).encode("utf-8")
            data = bytes(self.data).decode("utf-8", errors="replace").encode("utf-8")
            if len(data) + len(footer) > self.limit:
                self.truncated = True
                footer = ("\n[harness] output truncated\n" + notice).encode("utf-8")
            footer = footer[-self.limit:]
            prefix = data[:self.limit - len(footer)].decode("utf-8", errors="ignore").encode("utf-8")
            output = prefix + footer
            self.handle.seek(0)
            self.handle.write(output)
            self.handle.truncate()
            return output.decode("utf-8")
        finally:
            self.handle.close()


def run_logged_command(
    args: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None, *,
    timeout_seconds: float | None = 120, max_output_bytes: int = 8 * 1024 * 1024,
    markers: list[str] | None = None, require_all_markers: bool = False,
) -> subprocess.CompletedProcess[str]:
    timeout = 120 if timeout_seconds is None else timeout_seconds
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be finite and positive")
    if type(max_output_bytes) is not int or max_output_bytes <= 0:
        raise ValueError("max_output_bytes must be a positive integer")
    if markers is not None and (not markers or any(not isinstance(marker, str) or not marker for marker in markers)):
        raise ValueError("success_markers must contain non-empty strings")
    capture = None
    timed_out = False
    output = ""
    try:
        with OwnedProcess(args, cwd=str(cwd), env={**os.environ, **(env or {})}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0) as owned:
            process = owned.process
            capture = BoundedOutput(process.stdout, log_path, max_output_bytes, markers, require_all_markers)
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if markers is not None and capture.marker_found.is_set():
                    break
                if capture.error is not None:
                    raise RuntimeError(f"Failed to capture process output: {capture.error}") from capture.error
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                capture.marker_found.wait(min(remaining, 0.02))
            returncode = process.poll()
    except BaseException as original:
        if capture is not None:
            try:
                capture.finish()
            except BaseException as cleanup_error:
                original.add_note(f"Output cleanup failed: {cleanup_error}")
        raise
    else:
        notice = f"\n[harness] command timed out after {timeout:g} seconds\n" if timed_out else ""
        output = capture.finish(notice)
    marker_found = capture.marker_found.is_set()
    if timed_out:
        returncode = 124
    elif markers is not None:
        returncode = 0 if marker_found else (returncode or 1)
    result = subprocess.CompletedProcess(args=args, returncode=int(returncode or 0), stdout=output)
    result.output_truncated = capture.truncated
    result.timed_out = timed_out
    result.marker_found = marker_found
    return result
