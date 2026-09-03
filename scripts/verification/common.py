from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import hashlib
from pathlib import Path
from types import SimpleNamespace


DEFAULT_GODOT_EXE = Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def evidence_revision(project_root: Path | None = None) -> str:
    """Return a reproducible revision for committed or dirty-tree evidence."""
    root = project_root or repo_root()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=False).stdout.strip() or "unknown"
    status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=False).stdout
    if not status:
        return head
    return f"{head}+dirty:{hashlib.sha256(status.encode('utf-8')).hexdigest()[:16]}"


def verification_dir(project_root: Path) -> Path:
    path = project_root / ".harness" / "verification"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_godot_exe(explicit: str | None) -> Path:
    candidates = [explicit, os.environ.get("GODOT_EXE"), str(DEFAULT_GODOT_EXE)]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path
    raise FileNotFoundError("Godot executable not found. Set GODOT_EXE or pass --godot-exe.")


def resolve_python_exe(explicit: str | None) -> str:
    return explicit or os.environ.get("PYTHON_EXE") or sys.executable


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_markdown(path: Path, title: str, payload: dict[str, object], overall_key: str) -> None:
    lines = [f"# {title}", ""]
    lines.append(f"- Overall: `{payload.get(overall_key)}`")
    lines.append("")
    lines.append("| ID | Status | Title | Notes |")
    lines.append("| --- | --- | --- | --- |")
    for entry in payload.get("results", []):
        notes = str(entry.get("notes", "")).replace("\n", " ").strip()
        lines.append(
            f"| `{entry.get('id')}` | `{entry.get('status')}` | {entry.get('title')} | {notes} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_command(
    args: list[str],
    cwd: Path,
    log_path: Path,
    env: dict[str, str] | None = None,
    *,
    timeout_seconds: float | None = None,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    output_lines: list[str] = []

    def _reader() -> None:
        if process.stdout is None:
            return
        with log_path.open("w", encoding="utf-8") as log_handle:
            try:
                for line in iter(process.stdout.readline, ""):
                    output_lines.append(line)
                    log_handle.write(line)
                    log_handle.flush()
            finally:
                process.stdout.close()

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()
    timed_out = False
    try:
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5.0)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5.0)
        reader_thread.join(timeout=5.0)

    if timed_out:
        timeout_label = f"{timeout_seconds:g}" if timeout_seconds is not None else "unknown"
        timeout_message = f"[harness] command timed out after {timeout_label} seconds\n"
        output_lines.append(timeout_message)
        with log_path.open("a", encoding="utf-8") as log_handle:
            log_handle.write(timeout_message)
            log_handle.flush()

    return subprocess.CompletedProcess(
        args=args,
        returncode=124 if timed_out else int(process.returncode or 0),
        stdout="".join(output_lines),
    )


def run_command_until_markers(
    args: list[str],
    cwd: Path,
    log_path: Path,
    *,
    success_markers: list[str],
    timeout_seconds: float,
    env: dict[str, str] | None = None,
    require_all_markers: bool = False,
) -> SimpleNamespace:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    process = subprocess.Popen(
        args,
        cwd=str(cwd),
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    output_lines: list[str] = []
    line_queue: queue.Queue[str | None] = queue.Queue()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_path.open("w", encoding="utf-8")

    def _reader() -> None:
        if process.stdout is None:
            line_queue.put(None)
            return
        try:
            for line in iter(process.stdout.readline, ""):
                output_lines.append(line)
                log_handle.write(line)
                log_handle.flush()
                line_queue.put(line)
        finally:
            try:
                process.stdout.close()
            except Exception:
                pass
            try:
                log_handle.flush()
                log_handle.close()
            except Exception:
                pass
            line_queue.put(None)

    reader_thread = threading.Thread(target=_reader, daemon=True)
    reader_thread.start()
    marker_found = False
    found_markers: set[str] = set()
    deadline = time.time() + timeout_seconds
    try:
        while time.time() < deadline:
            if process.poll() is not None:
                break
            try:
                item = line_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if item is None:
                break
            for marker in success_markers:
                if marker in item:
                    found_markers.add(marker)
            if require_all_markers:
                if all(marker in found_markers for marker in success_markers):
                    marker_found = True
                    break
            elif found_markers:
                marker_found = True
                break
        if marker_found and process.poll() is None:
            process.terminate()
    finally:
        if process.poll() is None:
            process.kill()
        try:
            process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            pass
        reader_thread.join(timeout=5.0)
    output = "".join(output_lines)
    if not marker_found:
        if require_all_markers:
            marker_found = all(marker in output for marker in success_markers)
        else:
            marker_found = any(marker in output for marker in success_markers)
    return SimpleNamespace(
        returncode=0 if marker_found else (process.returncode if process.returncode is not None else 1),
        stdout=output,
        marker_found=marker_found,
    )


def ensure_godot_import(project_root: Path, godot_exe: Path, log_name: str = "godot-import.log") -> subprocess.CompletedProcess[str]:
    log_dir = verification_dir(project_root)
    log_path = log_dir / log_name
    return run_command(
        [
            str(godot_exe),
            "--path",
            str(project_root),
            "--import",
            "--quit",
            "--verbose",
            "--render-thread",
            "safe",
        ],
        project_root,
        log_path,
    )


def get_health(url: str = "http://127.0.0.1:8000/health") -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def _find_listener_pid(port: int) -> int | None:
    try:
        result = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-NetTCPConnection -LocalPort {port} -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess)",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None
    value = result.stdout.strip()
    if value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _terminate_listener_pid(pid: int) -> None:
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def wait_for_backend_release(
    *,
    port: int = 8000,
    timeout_seconds: float = 15.0,
    clear_observations_required: int = 2,
) -> bool:
    """Wait until the HTTP endpoint and its TCP listener are both stably gone."""
    deadline = time.time() + timeout_seconds
    clear_observations = 0
    while time.time() < deadline:
        if get_health() is None and _find_listener_pid(port) is None:
            clear_observations += 1
            if clear_observations >= clear_observations_required:
                return True
        else:
            clear_observations = 0
        time.sleep(0.1)
    return False


def ensure_backend(
    project_root: Path,
    python_exe: str,
    *,
    prefer_fresh_backend: bool = False,
    env: dict[str, str] | None = None,
) -> tuple[dict[str, object], subprocess.Popen[str] | None]:
    health = get_health()
    expected_root = str(project_root)
    if health is not None:
        if str(health.get("worktree_root", "")) == expected_root and not prefer_fresh_backend:
            return health, None
        if str(health.get("worktree_root", "")) == expected_root and prefer_fresh_backend:
            listener_pid = _find_listener_pid(8000)
            if listener_pid is not None:
                _terminate_listener_pid(listener_pid)
            if not wait_for_backend_release():
                raise RuntimeError("Backend port 8000 did not fully release within 15 seconds.")
            health = None
        elif str(health.get("worktree_root", "")) == expected_root:
            return health, None
    if health is not None:
        raise RuntimeError(
            f"Port 8000 is occupied by a different backend: {health.get('worktree_root', '')}"
        )

    log_dir = verification_dir(project_root)
    stdout_path = log_dir / "backend-verify.stdout.log"
    stderr_path = log_dir / "backend-verify.stderr.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(project_root / "backend"),
        env=merged_env,
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    deadline = time.time() + 45.0
    while time.time() < deadline:
        health = get_health()
        if health is not None and str(health.get("worktree_root", "")) == expected_root:
            return health, process
        time.sleep(0.25)
    process.terminate()
    raise RuntimeError("Backend did not become healthy on port 8000 within 15 seconds.")


def stop_backend(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def scan_direct_visual_fact_bypass(project_root: Path) -> str:
    suspicious: list[str] = []
    for path in (project_root / "scripts").rglob("*.gd"):
        text = read_text(path)
        normalized = str(path.relative_to(project_root)).replace("\\", "/")
        if "send_envelope(" not in text:
            continue
        if normalized.endswith("scripts/l1/facts/RawFactEmitter.gd"):
            continue
        if normalized.startswith("scripts/verification/"):
            continue
        if (
            "emit_visual_fact_event(" in text
            or '"message_type": "visual_fact_event"' in text
            or '"message_type": "raw_fact_event"' in text
            or '"event_type": "raw_fact_event"' in text
            or '"fact_family": "visual_fact"' in text
        ):
            suspicious.append(f"{normalized}:direct-visual-fact-send")
    player_intent_mapper = project_root / "scripts" / "player" / "PlayerIntentMapper.gd"
    if player_intent_mapper.exists():
        suspicious.append("scripts/player/PlayerIntentMapper.gd:visual-fact-envelope-builder")
    return "\n".join(suspicious)
