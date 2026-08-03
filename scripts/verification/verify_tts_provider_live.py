from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import settings
from app.services.tts_service import TTSProviderError, TTSService
from app.services.tts_voice_profiles import TTSVoiceBinding, TTSVoiceProfileError
from common import repo_root, verification_dir, write_json, write_markdown


_EVIDENCE_RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicit, redacted live TTS provider proof.")
    parser.add_argument("--allow-live-call", action="store_true", help="required before the script may contact a provider")
    parser.add_argument("--actor-id", action="append", dest="actor_ids", help="repeat for every approved actor binding")
    parser.add_argument("--evidence-run-id", default="", help="opaque approved ID shared with the Godot proof")
    args = parser.parse_args()

    actor_ids = args.actor_ids or ["char_a"]
    status, reason = _preflight(args.allow_live_call, args.evidence_run_id, actor_ids)
    results: list[dict[str, object]] = []
    if status == "ready":
        for actor_id in actor_ids:
            results.append(_synthesize_actor(actor_id))
        status = "real_provider_verified" if all(result["status"] == "real_provider_verified" for result in results) else "provider_fallback"
        reason = "complete_pcm_wav_clips" if status == "real_provider_verified" else "one_or_more_actor_proofs_failed"

    report = {
        "real_provider_status": status,
        "reason": reason,
        "evidence_run_id": args.evidence_run_id if _valid_evidence_run_id(args.evidence_run_id) else "",
        "live_call_opted_in": args.allow_live_call,
        "proof_class": "real_provider_live" if status == "real_provider_verified" else "not_live_complete",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "actor_results": results,
        "results": _report_results(status, reason, results),
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


def _preflight(allow_live_call: bool, evidence_run_id: str, actor_ids: list[str]) -> tuple[str, str]:
    if not allow_live_call:
        return "not_attempted", "explicit_opt_in_required"
    if not _valid_evidence_run_id(evidence_run_id):
        return "blocked_invalid_evidence_run_id", "opaque_evidence_run_id_required"
    if len(set(actor_ids)) != len(actor_ids) or not all(actor_id.strip() for actor_id in actor_ids):
        return "blocked_invalid_actor_set", "actor_ids_must_be_unique_and_nonblank"
    if settings.tts_mode not in {"openai_compatible", "dashscope_http"}:
        return "blocked_by_mode", "TTS_MODE=openai_compatible or TTS_MODE=dashscope_http is required for a live proof"
    if not settings.tts_provider_endpoint or not settings.tts_provider_api_key or not settings.tts_provider_model:
        return "blocked_missing_configuration", "provider endpoint, API key, and model are required"
    if not settings.tts_voice_profiles_enabled:
        return "blocked_profile_disabled", "TTS_VOICE_PROFILES_ENABLED=true is required for final-binding proof"
    return "ready", "preflight_passed"


def _synthesize_actor(actor_id: str) -> dict[str, object]:
    service = TTSService()
    try:
        binding = service.resolve_voice_binding(actor_id)
        if binding is None:
            return _actor_result(actor_id, "binding_rejected", "approved_binding_required")
        audio = service.synthesize(actor_id, "This is an explicit live TTS provider proof.")
    except (TTSProviderError, TTSVoiceProfileError):
        return _actor_result(actor_id, "binding_rejected", "binding_or_capability_preflight_failed")

    metadata = _binding_metadata(binding)
    if audio.mode != "clip" or audio.status != "ready":
        return _actor_result(actor_id, "provider_fallback", audio.fallback_reason or "provider_fallback", binding=metadata)
    if (
        audio.voice_id != binding.voice_id
        or audio.content_type != "audio/wav"
        or audio.encoding != "base64"
        or audio.sample_format != "pcm_s16le"
        or audio.sample_rate_hz != settings.tts_output_sample_rate_hz
        or audio.channels != 1
        or not audio.duration_ms
        or not audio.payload
    ):
        return _actor_result(actor_id, "provider_invalid_audio_contract", "ready_clip_metadata_mismatch", binding=metadata)

    wav_bytes = base64.b64decode(audio.payload, validate=True)
    return _actor_result(
        actor_id,
        "real_provider_verified",
        "complete_pcm_wav_clip",
        binding=metadata,
        audio={
            "contract": audio.contract,
            "provider": audio.provider,
            "voice_id": audio.voice_id,
            "content_type": audio.content_type,
            "sample_rate_hz": audio.sample_rate_hz,
            "channels": audio.channels,
            "sample_format": audio.sample_format,
            "duration_ms": audio.duration_ms,
            "byte_length": len(wav_bytes),
            "sha256": hashlib.sha256(wav_bytes).hexdigest(),
        },
    )


def _actor_result(
    actor_id: str,
    status: str,
    reason: str,
    *,
    binding: dict[str, object] | None = None,
    audio: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "status": status,
        "reason": reason,
        "binding": binding or {},
        "audio": audio or {},
    }


def _binding_metadata(binding: TTSVoiceBinding) -> dict[str, object]:
    identity = {
        "actor_id": binding.actor_id,
        "provider": binding.provider,
        "model": binding.model,
        "voice_id": binding.voice_id,
        "catalog_revision": binding.catalog_revision,
    }
    return {
        **identity,
        "approved": binding.selection_status == "approved",
        "approval_reference_present": bool(binding.approved_by and binding.approved_by.strip()),
        "identity_sha256": hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest(),
    }


def _report_results(status: str, reason: str, actor_results: list[dict[str, object]]) -> list[dict[str, object]]:
    if not actor_results:
        return [
            {
                "id": "live-provider-preflight",
                "status": "proved" if status == "real_provider_verified" else "missing",
                "title": "Live provider proof preflight",
                "notes": reason,
            }
        ]
    return [
        {
            "id": f"live-provider:{result['actor_id']}",
            "status": "proved" if result["status"] == "real_provider_verified" else "missing",
            "title": "Approved actor live synthesis",
            "notes": result["reason"],
        }
        for result in actor_results
    ]


def _valid_evidence_run_id(value: str) -> bool:
    return bool(_EVIDENCE_RUN_ID.fullmatch(value))


if __name__ == "__main__":
    raise SystemExit(main())
