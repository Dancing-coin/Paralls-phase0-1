from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import hashlib
from pathlib import Path
if __package__:
    from .process_control import BoundedOutput, OwnedProcess, run_logged_command
else:
    from process_control import BoundedOutput, OwnedProcess, run_logged_command
if __package__:
    from .run_context import current_run, output_root
else:
    from run_context import current_run, output_root


DEFAULT_GODOT_EXE = Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def evidence_revision(project_root: Path | None = None) -> str:
    """用 Git 基线和实际输入内容标识证据，状态文件名不代表内容。"""
    root = project_root or repo_root()
    def git(*args: str) -> bytes:
        result = subprocess.run(['git', *args], cwd=root, capture_output=True, check=False)
        if result.returncode != 0:
            raise RuntimeError('无法确定 Git 输入版本')
        return result.stdout
    head = git('rev-parse', 'HEAD').decode().strip()
    diff = git('diff', '--binary', 'HEAD', '--')
    untracked = git('ls-files', '--others', '--exclude-standard', '-z')
    if not diff and not untracked:
        return head
    digest = hashlib.sha256(diff)
    for raw in sorted(untracked.split(b'\0')):
        if not raw:
            continue
        path = root / os.fsdecode(raw)
        digest.update(raw + b'\0')
        if path.is_symlink():
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            with path.open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
        digest.update(b'\0')
    return f'{head}+dirty:{digest.hexdigest()}'


def verification_dir(project_root: Path) -> Path:
    path = output_root(project_root)
    path.mkdir(parents=True, exist_ok=True)
    return path


def artifact_path(project_root: Path, reference: str | Path) -> Path:
    """解析证据逻辑名；绝不从上一轮目录寻找结果。"""
    ref = str(reference).replace('\\', '/')
    if ref.startswith('harness-run:/'):
        root = current_run(project_root).evidence_root
        path = (root / ref[len('harness-run:/'):]).resolve()
        if not path.is_relative_to(root):
            raise ValueError('跨作用域证据引用越界')
        return path
    prefix = '.harness/verification/'
    if ref.startswith(prefix):
        relative = ref[len(prefix):]
        root = verification_dir(project_root)
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('证据引用越界')
        run = current_run(project_root)
        if not path.exists():
            # 只沿当前运行的作用域索引查依赖，不扫描历史目录或旧 attempt。
            for scope in (root, *root.parents):
                if not scope.is_relative_to(run.evidence_root):
                    break
                index_path = scope / '.harness-artifacts.json'
                if not index_path.exists():
                    continue
                index = json.loads(index_path.read_text(encoding='utf-8'))
                if index.get('run_id') != run.run_id:
                    raise ValueError('证据映射不属于本轮')
                mapped = index.get('artifacts', {}).get(relative)
                if mapped:
                    path = (scope / str(mapped)).resolve()
                    if not path.is_relative_to(scope):
                        raise ValueError('证据映射越界')
                    break
        return path
    path = (project_root / ref).resolve()
    if not path.is_relative_to(project_root.resolve()):
        raise ValueError('源码引用越界')
    return path


def artifact_ref(project_root: Path, path: Path) -> str:
    path = path.resolve()
    if path.is_relative_to(project_root.resolve()):
        return path.relative_to(project_root.resolve()).as_posix()
    root = verification_dir(project_root)
    if not path.is_relative_to(root):
        run_root = current_run(project_root).evidence_root
        if path.is_relative_to(run_root):
            return 'harness-run:/' + path.relative_to(run_root).as_posix()
        raise ValueError(f'证据引用不属于当前运行: {path}')
    return '.harness/verification/' + path.relative_to(root).as_posix()


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
    timeout_seconds: float | None = 120,
    max_output_bytes: int = 8 * 1024 * 1024,
) -> subprocess.CompletedProcess[str]:
    return run_logged_command(args, cwd, log_path, env, timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes)


def run_command_until_markers(
    args: list[str],
    cwd: Path,
    log_path: Path,
    *,
    success_markers: list[str],
    timeout_seconds: float,
    env: dict[str, str] | None = None,
    require_all_markers: bool = False,
    max_output_bytes: int = 8 * 1024 * 1024,
) -> subprocess.CompletedProcess[str]:
    return run_logged_command(
        args, cwd, log_path, env, timeout_seconds=timeout_seconds, max_output_bytes=max_output_bytes,
        markers=success_markers, require_all_markers=require_all_markers,
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
        raise RuntimeError(
            f"Port 8000 is occupied by an existing backend; only its owner may stop it: {health.get('worktree_root', '')}"
        )
    if _find_listener_pid(8000) is not None:
        raise RuntimeError("Port 8000 is occupied by an external process without a healthy backend")

    log_dir = verification_dir(project_root)
    stdout_path = log_dir / "backend-verify.stdout.log"
    stderr_path = log_dir / "backend-verify.stderr.log"
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    owner = OwnedProcess(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(project_root / "backend"),
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
    )
    process = owner.process
    process._harness_output_captures = []
    try:
        for stream, path in [(process.stdout, stdout_path), (process.stderr, stderr_path)]:
            process._harness_output_captures.append(BoundedOutput(stream, path, 8 * 1024 * 1024))
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Owned backend exited before becoming healthy: {process.returncode}")
            health = get_health()
            if health is not None and str(health.get("worktree_root", "")) == expected_root:
                return health, process
            time.sleep(0.25)
        raise RuntimeError("Backend did not become healthy on port 8000 within 45 seconds")
    except BaseException as original:
        try:
            stop_backend(process)
        except BaseException as cleanup_error:
            original.add_note(f"Backend startup cleanup failed: {cleanup_error}")
        raise


def stop_backend(process: subprocess.Popen[str] | None) -> None:
    if process is None:
        return
    owner = getattr(process, "_harness_owner", None)
    errors: list[str] = []
    try:
        if owner is not None:
            owner.close()
        elif process.poll() is None:
            # 调用方显式传来的 Popen 仅按该句柄终止，不通过端口查杀进程。
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    except Exception as error:
        errors.append(str(error))
    for capture in getattr(process, "_harness_output_captures", []):
        try:
            capture.finish()
        except Exception as error:
            errors.append(str(error))
    process._harness_output_captures = []
    if errors:
        raise RuntimeError("Backend cleanup failed: " + "; ".join(errors))


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
