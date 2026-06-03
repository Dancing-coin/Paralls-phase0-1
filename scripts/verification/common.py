from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_GODOT_EXE = Path(r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def verification_dir(project_root: Path) -> Path:
    path = project_root / ".omx" / "verification"
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


def run_command(args: list[str], cwd: Path, log_path: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    result = subprocess.run(
        args,
        cwd=str(cwd),
        env=merged_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(result.stdout, encoding="utf-8")
    return result


def get_health(url: str = "http://127.0.0.1:8000/health") -> dict[str, object] | None:
    try:
        with urllib.request.urlopen(url, timeout=1.0) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None


def ensure_backend(project_root: Path, python_exe: str) -> tuple[dict[str, object], subprocess.Popen[str] | None]:
    health = get_health()
    expected_root = str(project_root)
    if health is not None:
        if str(health.get("worktree_root", "")) == expected_root:
            return health, None
        raise RuntimeError(
            f"Port 8000 is occupied by a different backend: {health.get('worktree_root', '')}"
        )

    log_dir = verification_dir(project_root)
    stdout_path = log_dir / "backend-verify.stdout.log"
    stderr_path = log_dir / "backend-verify.stderr.log"
    stdout_handle = stdout_path.open("w", encoding="utf-8")
    stderr_handle = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        [python_exe, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(project_root / "backend"),
        stdout=stdout_handle,
        stderr=stderr_handle,
        text=True,
    )
    deadline = time.time() + 15.0
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
        if normalized.endswith("scripts/visual/VisualFactEmitter.gd"):
            suspicious.append(f"{normalized}:allowed-emitter-send")
            continue
        if "emit_visual_fact_event(" in text or '"message_type": "visual_fact_event"' in text:
            suspicious.append(f"{normalized}:direct-visual-fact-send")
    player_intent_mapper = project_root / "scripts" / "player" / "PlayerIntentMapper.gd"
    if player_intent_mapper.exists():
        suspicious.append("scripts/player/PlayerIntentMapper.gd:visual-fact-envelope-builder")
    return "\n".join(suspicious)
