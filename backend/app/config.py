import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


SimingLlmProviderName = Literal["disabled", "openai_responses", "deepseek_chat", "seed_doubao", "qwen"]


class SimingLlmRouteSettings(BaseModel):
    route_id: str
    provider: SimingLlmProviderName
    model: str | None = None
    endpoint: str | None = None
    api_key: str | None = Field(default=None, repr=False, exclude=True)
    timeout_seconds: float | None = Field(default=None, gt=0)
    enabled: bool = True


class Settings(BaseModel):
    dialogue_mode: str = "stub"
    tts_mode: Literal["stub", "openai_compatible", "dashscope_http"] = "stub"
    tts_provider_endpoint: str | None = None
    tts_provider_api_key: str | None = Field(default=None, repr=False, exclude=True)
    tts_provider_model: str | None = None
    tts_provider_timeout_seconds: float = Field(default=15.0, gt=0)
    tts_default_voice: str = "default"
    tts_voice_map: dict[str, str] = Field(default_factory=dict)
    tts_voice_profiles_enabled: bool = False
    tts_presentation_instructions_enabled: bool = False
    tts_voice_catalog_path: str | None = None
    tts_voice_bindings_path: str | None = None
    tts_voice_required_language: str | None = None
    tts_voice_enrollment_endpoint: str | None = None
    tts_output_sample_rate_hz: int = Field(default=24000, ge=8000, le=48000)
    tts_max_encoded_payload_bytes: int = Field(default=1_000_000, ge=1, le=1_000_000)
    character_dialogue_cascade_limit: int = Field(default=180, ge=1)
    character_model_provider_kind: str = "qwen"
    character_model_endpoint: str | None = None
    character_model_api_key: str | None = Field(default=None, repr=False, exclude=True)
    character_model_model: str | None = None
    character_model_timeout_seconds: float = Field(default=20.0, gt=0)
    siming_llm_mode: Literal["disabled", "http"] = "disabled"
    siming_llm_api_key: str | None = Field(default=None, repr=False, exclude=True)
    siming_llm_endpoint: str = "https://api.openai.com/v1/responses"
    siming_llm_model: str = "gpt-5.4-mini"
    siming_llm_timeout_seconds: float = Field(default=8.0, gt=0)
    siming_llm_provider_order: list[SimingLlmProviderName] = Field(default_factory=lambda: ["openai_responses"])
    siming_llm_routes: list[SimingLlmRouteSettings] = Field(default_factory=list)
    vla_provider_mode: Literal["disabled", "http", "local", "blocked"] = "blocked"
    vla_provider_kind: Literal["openai_compatible"] = "openai_compatible"
    vla_provider_endpoint: str | None = None
    vla_provider_api_key: str | None = Field(default=None, repr=False, exclude=True)
    vla_provider_model: str = "qwen3-vl-plus"
    vla_provider_model_version: str = "configured-unverified"
    vla_provider_timeout_seconds: float = Field(default=8.0, gt=0)
    vla_provider_json_mode_enabled: bool = False
    vla_advisory_fast_model: str = "qwen3.7-flash"
    vla_advisory_fast_model_version: str = "configured-unverified"
    vla_advisory_fast_timeout_seconds: float = Field(default=12.0, gt=0)
    vla_advisory_fast_enable_thinking: bool = False
    vla_advisory_deep_enabled: bool = False
    vla_advisory_deep_model: str = "qwen3.7-plus"
    vla_advisory_deep_model_version: str = "configured-unverified"
    vla_advisory_deep_timeout_seconds: float = Field(default=20.0, gt=0)
    vla_advisory_deep_enable_thinking: bool = True
    vla_advisory_deep_confidence_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    vla_provider_max_queue_size: int = 8
    vla_provider_cache_ttl_seconds: float = 30.0
    vla_provider_required_artifact_refs: str = ""
    vla_live_proof_image_url: str | None = None
    vla_live_proof_image_path: str | None = None
    vla_live_proof_artifact_ref: str = "visual_artifact:vla-live-proof"
    vla_provider_live_proof_run_id: str = ""
    gameplay_mirror_phase3_actor_configs: list[dict[str, object]] = Field(default_factory=list)
    non_runtime_model_mode: Literal["disabled", "http", "local", "blocked"] = "disabled"
    non_runtime_model_endpoint: str | None = None
    non_runtime_model_api_key: str | None = Field(default=None, repr=False, exclude=True)
    non_runtime_model_model: str = "doubao-seed-2.0-lite"
    non_runtime_model_timeout_seconds: float = Field(default=30.0, gt=0)


def _read_project_env() -> dict[str, str]:
    values: dict[str, str] = {}
    project_root = Path(__file__).resolve().parents[2]
    for env_path in [project_root / ".env", project_root / ".env.vla", project_root / ".env.tts"]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            values[key] = value.strip().strip('"').strip("'")
    return values


_project_env = _read_project_env()


def _env_value(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, _project_env.get(name, default))


def _env_list(name: str, default: list[str]) -> list[str]:
    value = _env_value(name)
    if value is None:
        return list(default)
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or list(default)


def _env_optional(name: str) -> str | None:
    value = _env_value(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _env_bool(name: str, default: bool) -> bool:
    value = _env_value(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be one of true/false, 1/0, yes/no, or on/off")


def _env_siming_llm_routes() -> list[SimingLlmRouteSettings]:
    value = _env_value("SIMING_LLM_ROUTES_JSON")
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("SIMING_LLM_ROUTES_JSON must be a JSON array")
    return [SimingLlmRouteSettings.model_validate(item) for item in parsed]


def _env_tts_voice_map() -> dict[str, str]:
    value = _env_value("TTS_VOICE_MAP_JSON")
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in parsed.items()):
        raise ValueError("TTS_VOICE_MAP_JSON must be a JSON object mapping actor IDs to voice IDs")
    return parsed


def _env_object_list(name: str) -> list[dict[str, object]]:
    value = _env_value(name)
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ValueError(f"{name} must be a JSON array of objects")
    return [dict(item) for item in parsed]


settings = Settings(
    dialogue_mode=_env_value("DIALOGUE_MODE", "stub") or "stub",
    tts_mode=_env_value("TTS_MODE", "stub") or "stub",
    tts_provider_endpoint=_env_optional("TTS_PROVIDER_ENDPOINT"),
    tts_provider_api_key=_env_optional("TTS_PROVIDER_API_KEY"),
    tts_provider_model=_env_optional("TTS_PROVIDER_MODEL"),
    tts_provider_timeout_seconds=float(_env_value("TTS_PROVIDER_TIMEOUT_SECONDS", "15") or "15"),
    tts_default_voice=_env_value("TTS_DEFAULT_VOICE", "default") or "default",
    tts_voice_map=_env_tts_voice_map(),
    tts_voice_profiles_enabled=_env_bool("TTS_VOICE_PROFILES_ENABLED", False),
    tts_presentation_instructions_enabled=_env_bool("TTS_PRESENTATION_INSTRUCTIONS_ENABLED", False),
    tts_voice_catalog_path=_env_optional("TTS_VOICE_CATALOG_PATH"),
    tts_voice_bindings_path=_env_optional("TTS_VOICE_BINDINGS_PATH"),
    tts_voice_required_language=_env_optional("TTS_VOICE_REQUIRED_LANGUAGE"),
    tts_voice_enrollment_endpoint=_env_optional("TTS_VOICE_ENROLLMENT_ENDPOINT"),
    tts_output_sample_rate_hz=int(_env_value("TTS_OUTPUT_SAMPLE_RATE_HZ", "24000") or "24000"),
    tts_max_encoded_payload_bytes=int(_env_value("TTS_MAX_ENCODED_PAYLOAD_BYTES", "1000000") or "1000000"),
    character_dialogue_cascade_limit=int(_env_value("CHARACTER_DIALOGUE_CASCADE_LIMIT", "180") or "180"),
    character_model_provider_kind=_env_value("CHARACTER_MODEL_PROVIDER_KIND", "qwen") or "qwen",
    character_model_endpoint=_env_optional("CHARACTER_MODEL_ENDPOINT"),
    character_model_api_key=_env_optional("CHARACTER_MODEL_API_KEY"),
    character_model_model=_env_optional("CHARACTER_MODEL_MODEL"),
    character_model_timeout_seconds=float(_env_value("CHARACTER_MODEL_TIMEOUT_SECONDS", "20.0") or "20.0"),
    siming_llm_mode=_env_value("SIMING_LLM_MODE", "disabled") or "disabled",
    siming_llm_api_key=_env_value("SIMING_LLM_API_KEY"),
    siming_llm_endpoint=_env_value("SIMING_LLM_ENDPOINT", "https://api.openai.com/v1/responses")
    or "https://api.openai.com/v1/responses",
    siming_llm_model=_env_value("SIMING_LLM_MODEL", "gpt-5.4-mini") or "gpt-5.4-mini",
    siming_llm_timeout_seconds=float(_env_value("SIMING_LLM_TIMEOUT_SECONDS", "8.0") or "8.0"),
    siming_llm_provider_order=_env_list(
        "SIMING_LLM_PROVIDER_ORDER",
        [] if _env_value("SIMING_LLM_ROUTES_JSON") else ["openai_responses"],
    ),
    siming_llm_routes=_env_siming_llm_routes(),
    vla_provider_mode=_env_value("VLA_PROVIDER_MODE", "blocked") or "blocked",
    vla_provider_kind=_env_value("VLA_PROVIDER_KIND", "openai_compatible") or "openai_compatible",
    vla_provider_endpoint=_env_value("VLA_PROVIDER_ENDPOINT"),
    vla_provider_api_key=_env_value("VLA_PROVIDER_API_KEY"),
    vla_provider_model=_env_value("VLA_PROVIDER_MODEL", "qwen3-vl-plus") or "qwen3-vl-plus",
    vla_provider_model_version=_env_value("VLA_PROVIDER_MODEL_VERSION", "configured-unverified") or "configured-unverified",
    vla_provider_timeout_seconds=float(_env_value("VLA_PROVIDER_TIMEOUT_SECONDS", "8.0") or "8.0"),
    vla_provider_json_mode_enabled=_env_bool("VLA_PROVIDER_JSON_MODE_ENABLED", False),
    vla_advisory_fast_model=_env_value("VLA_ADVISORY_FAST_MODEL", "qwen3.7-flash") or "qwen3.7-flash",
    vla_advisory_fast_model_version=_env_value("VLA_ADVISORY_FAST_MODEL_VERSION", "configured-unverified") or "configured-unverified",
    vla_advisory_fast_timeout_seconds=float(_env_value("VLA_ADVISORY_FAST_TIMEOUT_SECONDS", "12.0") or "12.0"),
    vla_advisory_fast_enable_thinking=_env_bool("VLA_ADVISORY_FAST_ENABLE_THINKING", False),
    vla_advisory_deep_enabled=_env_bool("VLA_ADVISORY_DEEP_ENABLED", False),
    vla_advisory_deep_model=_env_value("VLA_ADVISORY_DEEP_MODEL", "qwen3.7-plus") or "qwen3.7-plus",
    vla_advisory_deep_model_version=_env_value("VLA_ADVISORY_DEEP_MODEL_VERSION", "configured-unverified") or "configured-unverified",
    vla_advisory_deep_timeout_seconds=float(_env_value("VLA_ADVISORY_DEEP_TIMEOUT_SECONDS", "20.0") or "20.0"),
    vla_advisory_deep_enable_thinking=_env_bool("VLA_ADVISORY_DEEP_ENABLE_THINKING", True),
    vla_advisory_deep_confidence_threshold=float(_env_value("VLA_ADVISORY_DEEP_CONFIDENCE_THRESHOLD", "0.55") or "0.55"),
    vla_provider_max_queue_size=int(_env_value("VLA_PROVIDER_MAX_QUEUE_SIZE", "8") or "8"),
    vla_provider_cache_ttl_seconds=float(_env_value("VLA_PROVIDER_CACHE_TTL_SECONDS", "30.0") or "30.0"),
    vla_provider_required_artifact_refs=_env_value("VLA_PROVIDER_REQUIRED_ARTIFACT_REFS", "") or "",
    vla_live_proof_image_url=_env_optional("VLA_LIVE_PROOF_IMAGE_URL"),
    vla_live_proof_image_path=_env_optional("VLA_LIVE_PROOF_IMAGE_PATH"),
    vla_live_proof_artifact_ref=_env_value("VLA_LIVE_PROOF_ARTIFACT_REF", "visual_artifact:vla-live-proof")
    or "visual_artifact:vla-live-proof",
    vla_provider_live_proof_run_id=_env_value("VLA_PROVIDER_LIVE_PROOF_RUN_ID", "") or "",
    gameplay_mirror_phase3_actor_configs=_env_object_list("GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON"),
    non_runtime_model_mode=_env_value("NON_RUNTIME_MODEL_MODE", "disabled") or "disabled",
    non_runtime_model_endpoint=_env_value("NON_RUNTIME_MODEL_ENDPOINT"),
    non_runtime_model_api_key=_env_value("NON_RUNTIME_MODEL_API_KEY"),
    non_runtime_model_model=_env_value("NON_RUNTIME_MODEL_MODEL", "doubao-seed-2.0-lite") or "doubao-seed-2.0-lite",
    non_runtime_model_timeout_seconds=float(_env_value("NON_RUNTIME_MODEL_TIMEOUT_SECONDS", "30.0") or "30.0"),
)
