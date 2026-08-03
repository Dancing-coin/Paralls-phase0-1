from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import settings
from app.services.tts_service import TTSProviderError, TTSService
from app.services.tts_voice_profiles import TTSVoiceProfileError
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
from verify_tts_provider_live import _binding_metadata, _preflight


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicit, redacted DashScope-to-Godot TTS playback proof.")
    parser.add_argument("--allow-live-call", action="store_true", help="required before the probe may synthesize audio")
    parser.add_argument("--actor-id", action="append", dest="actor_ids", help="repeat for every approved actor binding")
    parser.add_argument("--evidence-run-id", default="", help="opaque approved ID shared with the provider proof")
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    actor_ids = args.actor_ids or ["char_a"]
    status, reason = _preflight(args.allow_live_call, args.evidence_run_id, actor_ids)
    if status == "ready" and settings.tts_mode != "dashscope_http":
        status, reason = "blocked_by_mode", "TTS_MODE=dashscope_http is required for Godot live playback proof"

    project_root = repo_root()
    evidence_dir = verification_dir(project_root)
    results: list[dict[str, object]] = []
    backend_process = None
    try:
        if status == "ready":
            python_exe = resolve_python_exe(args.python_exe)
            godot_exe = resolve_godot_exe(args.godot_exe)
            _, backend_process = ensure_backend(
                project_root,
                python_exe,
                prefer_fresh_backend=True,
                env={"CHARACTER_MODEL_PROVIDER_KIND": "local", "CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only"},
            )
            for actor_id in actor_ids:
                results.append(_run_actor(project_root, evidence_dir, godot_exe, actor_id, args.evidence_run_id))
            status = (
                "real_godot_playback_verified"
                if all(result["status"] == "real_godot_playback_verified" for result in results)
                else "godot_playback_failed"
            )
            reason = "spatial_voice_controller_played_final_binding_clips" if status == "real_godot_playback_verified" else "one_or_more_actor_proofs_failed"
    except (FileNotFoundError, RuntimeError) as exc:
        status, reason = "godot_playback_failed", type(exc).__name__
    finally:
        stop_backend(backend_process)

    report = {
        "godot_tts_playback_status": status,
        "reason": reason,
        "evidence_run_id": args.evidence_run_id if status not in {"not_attempted", "blocked_invalid_evidence_run_id"} else "",
        "live_call_opted_in": args.allow_live_call,
        "proof_class": "godot_runtime_playback" if status == "real_godot_playback_verified" else "not_godot_complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "actor_results": results,
        "results": _report_results(status, reason, results),
    }
    json_path = evidence_dir / "tts-godot-live-playback-report.json"
    markdown_path = evidence_dir / "tts-godot-live-playback-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "TTS Godot Playback Proof", report, "godot_tts_playback_status")
    print(f"tts_godot_playback_report_json={json_path}")
    print(f"tts_godot_playback_report_md={markdown_path}")
    print(f"godot_tts_playback_status={status}")
    return 0 if status == "real_godot_playback_verified" else 1


def _run_actor(project_root: Path, evidence_dir: Path, godot_exe: Path, actor_id: str, evidence_run_id: str) -> dict[str, object]:
    try:
        binding = TTSService().resolve_voice_binding(actor_id)
    except (TTSProviderError, TTSVoiceProfileError):
        return _actor_result(actor_id, "binding_rejected", "binding_or_capability_preflight_failed")
    if binding is None:
        return _actor_result(actor_id, "binding_rejected", "approved_binding_required")

    log_path = evidence_dir / f"tts-godot-live-playback-{actor_id}.log"
    marker = f"tts_godot_playback_verified:actor={actor_id}:provider=dashscope_http"
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
            "--",
            "--actor-id",
            actor_id,
            "--expected-voice-id",
            binding.voice_id,
            "--evidence-run-id",
            evidence_run_id,
        ],
        project_root,
        log_path,
        success_markers=[marker],
        timeout_seconds=75.0,
    )
    log = read_text(log_path)
    succeeded = result.returncode == 0 and marker in log and "voice_clip_rejected" not in log and "voice_stub_played" not in log
    return _actor_result(
        actor_id,
        "real_godot_playback_verified" if succeeded else "godot_playback_failed",
        "spatial_voice_controller_played_complete_clip" if succeeded else _failure_reason(log),
        binding=_binding_metadata(binding),
        log_artifact=str(log_path.relative_to(project_root)).replace("\\", "/"),
    )


def _actor_result(
    actor_id: str,
    status: str,
    reason: str,
    *,
    binding: dict[str, object] | None = None,
    log_artifact: str = "",
) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "status": status,
        "reason": reason,
        "binding": binding or {},
        "log_artifact": log_artifact,
    }


def _failure_reason(log: str) -> str:
    for line in reversed(log.splitlines()):
        if "tts_godot_playback_failed:" in line:
            return line.split("tts_godot_playback_failed:", 1)[1].strip() or "godot_playback_failed"
    return "godot_playback_failed"


def _report_results(status: str, reason: str, actor_results: list[dict[str, object]]) -> list[dict[str, object]]:
    if not actor_results:
        return [
            {
                "id": "godot-playback-preflight",
                "status": "proved" if status == "real_godot_playback_verified" else "missing",
                "title": "Godot playback proof preflight",
                "notes": reason,
            }
        ]
    return [
        {
            "id": f"godot-playback:{result['actor_id']}",
            "status": "proved" if result["status"] == "real_godot_playback_verified" else "missing",
            "title": "Approved actor real-payload playback",
            "notes": result["reason"],
        }
        for result in actor_results
    ]


if __name__ == "__main__":
    raise SystemExit(main())
