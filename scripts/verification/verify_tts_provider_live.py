from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import settings
from app.services.tts_service import TTSService
from common import repo_root, verification_dir, write_json, write_markdown


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicit live TTS provider proof.")
    parser.add_argument("--allow-live-call", action="store_true", help="required before the script may contact a provider")
    parser.add_argument("--actor-id", default="char_a")
    args = parser.parse_args()

    status = "not_attempted"
    reason = "explicit_opt_in_required"
    proof: dict[str, object] = {}
    if args.allow_live_call:
        if settings.tts_mode not in {"openai_compatible", "dashscope_http"}:
            status = "blocked_by_mode"
            reason = "TTS_MODE=openai_compatible or TTS_MODE=dashscope_http is required for a live proof"
        elif not settings.tts_provider_endpoint or not settings.tts_provider_api_key or not settings.tts_provider_model:
            status = "blocked_missing_configuration"
            reason = "TTS_PROVIDER_ENDPOINT, TTS_PROVIDER_API_KEY, and TTS_PROVIDER_MODEL are required"
        elif _has_unexpanded_workspace_id(settings.tts_provider_endpoint):
            status = "blocked_missing_configuration"
            reason = "TTS_PROVIDER_ENDPOINT must replace the DashScope workspace placeholder without braces"
        else:
            audio = TTSService().synthesize(args.actor_id, "This is an explicit live TTS provider proof.")
            status = "real_provider_verified" if audio.mode == "clip" and audio.status == "ready" else "provider_fallback"
            reason = "complete_pcm_wav_clip" if status == "real_provider_verified" else audio.fallback_reason or "provider_fallback"
            proof = {
                "audio_contract": audio.contract,
                "mode": audio.mode,
                "status": audio.status,
                "provider": audio.provider,
                "voice_id": audio.voice_id,
                "content_type": audio.content_type,
                "sample_rate_hz": audio.sample_rate_hz,
                "channels": audio.channels,
                "duration_ms": audio.duration_ms,
            }

    report = {
        "real_provider_status": status,
        "reason": reason,
        "endpoint_host": _endpoint_host(settings.tts_provider_endpoint or ""),
        "model_id": settings.tts_provider_model or "not_configured",
        "live_call_opted_in": args.allow_live_call,
        "proof": proof,
    }
    evidence_dir = verification_dir(repo_root())
    json_path = evidence_dir / "tts-provider-live-report.json"
    markdown_path = evidence_dir / "tts-provider-live-report.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "TTS Provider Live Proof", report, "real_provider_status")
    print(f"tts_provider_live_report_json={json_path}")
    print(f"tts_provider_live_report_md={markdown_path}")
    print(f"real_provider_status={status}")
    return 0 if status == "real_provider_verified" else 1


def _endpoint_host(endpoint: str) -> str:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return parsed.hostname or "not_configured"


def _has_unexpanded_workspace_id(endpoint: str) -> bool:
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return not parsed.netloc or "{" in parsed.netloc or "}" in parsed.netloc


if __name__ == "__main__":
    raise SystemExit(main())
