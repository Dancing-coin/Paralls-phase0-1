from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import settings
from common import (
    ensure_backend,
    read_text,
    repo_root,
    resolve_godot_exe,
    resolve_python_exe,
    run_command_until_markers,
    stop_backend,
    verification_dir,
    write_json,
    write_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicit DashScope-to-Godot TTS playback proof.")
    parser.add_argument("--allow-live-call", action="store_true", help="required before the probe may synthesize audio")
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    evidence_dir = verification_dir(project_root)
    status = "not_attempted"
    reason = "explicit_opt_in_required"
    proof: dict[str, object] = {}
    backend_process = None
    try:
        if not args.allow_live_call:
            return _write_report(evidence_dir, status, reason, proof)
        if settings.tts_mode != "dashscope_http":
            return _write_report(evidence_dir, "blocked_by_mode", "TTS_MODE=dashscope_http is required", proof)
        if not settings.tts_provider_endpoint or not settings.tts_provider_api_key or not settings.tts_provider_model:
            return _write_report(evidence_dir, "blocked_missing_configuration", "DashScope TTS configuration is incomplete", proof)

        python_exe = resolve_python_exe(args.python_exe)
        godot_exe = resolve_godot_exe(args.godot_exe)
        _, backend_process = ensure_backend(
            project_root,
            python_exe,
            prefer_fresh_backend=True,
            env={"CHARACTER_MODEL_PROVIDER_KIND": "local", "CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only"},
        )
        log_path = evidence_dir / "tts-godot-live-playback.log"
        result = run_command_until_markers(
            [
                str(godot_exe),
                "--headless",
                "--path",
                str(project_root),
                "--script",
                "res://scripts/verification/TTSGodotLivePlaybackProbe.gd",
                "--render-thread",
                "safe",
            ],
            project_root,
            log_path,
            success_markers=["tts_godot_playback_verified:provider=dashscope_http"],
            timeout_seconds=75.0,
        )
        log = read_text(log_path)
        succeeded = result.returncode == 0 and "tts_godot_playback_verified:provider=dashscope_http" in log
        status = "real_godot_playback_verified" if succeeded else "godot_playback_failed"
        reason = "spatial_voice_controller_played_dashscope_clip" if succeeded else _failure_reason(log)
        proof = {
            "marker_found": succeeded,
            "clip_rejected": "voice_clip_rejected" in log,
            "stub_played": "voice_stub_played" in log,
            "log_path": str(log_path),
        }
        return _write_report(evidence_dir, status, reason, proof)
    finally:
        stop_backend(backend_process)


def _failure_reason(log: str) -> str:
    for line in reversed(log.splitlines()):
        if "tts_godot_playback_failed:" in line:
            return line.split("tts_godot_playback_failed:", 1)[1].strip() or "godot_playback_failed"
    return "godot_playback_failed"


def _write_report(evidence_dir: Path, status: str, reason: str, proof: dict[str, object]) -> int:
    report = {
        "godot_tts_playback_status": status,
        "reason": reason,
        "provider_mode": settings.tts_mode,
        "model_id": settings.tts_provider_model or "not_configured",
        "proof": proof,
    }
    json_path = evidence_dir / "tts-godot-live-playback-report.json"
    markdown_path = evidence_dir / "tts-godot-live-playback-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "TTS Godot Playback Proof", report, "godot_tts_playback_status")
    print(f"tts_godot_playback_report_json={json_path}")
    print(f"tts_godot_playback_report_md={markdown_path}")
    print(f"godot_tts_playback_status={status}")
    return 0 if status == "real_godot_playback_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
