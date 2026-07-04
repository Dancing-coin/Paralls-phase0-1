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
    timeout_seconds: float | None = None
    enabled: bool = True


class Settings(BaseModel):
    dialogue_mode: str = "stub"
    tts_mode: str = "stub"
    character_model_provider_kind: str = "qwen"
    character_model_endpoint: str | None = None
    character_model_api_key: str | None = Field(default=None, repr=False, exclude=True)
    character_model_model: str = "qwen3.7-plus"
    character_model_timeout_seconds: float = 20.0
    siming_llm_mode: Literal["disabled", "http"] = "disabled"
    siming_llm_api_key: str | None = Field(default=None, repr=False, exclude=True)
    siming_llm_endpoint: str = "https://api.openai.com/v1/responses"
    siming_llm_model: str = "gpt-5.4-mini"
    siming_llm_timeout_seconds: float = 8.0
    siming_llm_provider_order: list[SimingLlmProviderName] = Field(default_factory=lambda: ["openai_responses"])
    siming_llm_routes: list[SimingLlmRouteSettings] = Field(default_factory=list)
    vla_provider_mode: Literal["disabled", "http", "local", "blocked"] = "blocked"
    vla_provider_endpoint: str | None = None
    vla_provider_api_key: str | None = Field(default=None, repr=False, exclude=True)
    vla_provider_model: str = "qwen3-vl-plus"
    vla_provider_timeout_seconds: float = 8.0
    vla_provider_max_queue_size: int = 8
    vla_provider_cache_ttl_seconds: float = 30.0
    non_runtime_model_mode: Literal["disabled", "http", "local", "blocked"] = "disabled"
    non_runtime_model_endpoint: str | None = None
    non_runtime_model_api_key: str | None = Field(default=None, repr=False, exclude=True)
    non_runtime_model_model: str = "doubao-seed-2.0-lite"
    non_runtime_model_timeout_seconds: float = 30.0


def _read_project_env() -> dict[str, str]:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
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


def _env_siming_llm_routes() -> list[SimingLlmRouteSettings]:
    value = _env_value("SIMING_LLM_ROUTES_JSON")
    if not value:
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError("SIMING_LLM_ROUTES_JSON must be a JSON array")
    return [SimingLlmRouteSettings.model_validate(item) for item in parsed]


settings = Settings(
    dialogue_mode=_env_value("DIALOGUE_MODE", "stub") or "stub",
    tts_mode=_env_value("TTS_MODE", "stub") or "stub",
    character_model_provider_kind=_env_value("CHARACTER_MODEL_PROVIDER_KIND", "qwen") or "qwen",
    character_model_endpoint=_env_value("CHARACTER_MODEL_ENDPOINT"),
    character_model_api_key=_env_value("CHARACTER_MODEL_API_KEY"),
    character_model_model=_env_value("CHARACTER_MODEL_MODEL", "qwen3.7-plus") or "qwen3.7-plus",
    character_model_timeout_seconds=float(_env_value("CHARACTER_MODEL_TIMEOUT_SECONDS", "20.0") or "20.0"),
    siming_llm_mode=_env_value("SIMING_LLM_MODE", "disabled") or "disabled",
    siming_llm_api_key=_env_value("SIMING_LLM_API_KEY"),
    siming_llm_endpoint=_env_value("SIMING_LLM_ENDPOINT", "https://api.openai.com/v1/responses")
    or "https://api.openai.com/v1/responses",
    siming_llm_model=_env_value("SIMING_LLM_MODEL", "gpt-5.4-mini") or "gpt-5.4-mini",
    siming_llm_timeout_seconds=float(_env_value("SIMING_LLM_TIMEOUT_SECONDS", "8.0") or "8.0"),
    siming_llm_provider_order=_env_list("SIMING_LLM_PROVIDER_ORDER", ["openai_responses"]),
    siming_llm_routes=_env_siming_llm_routes(),
    vla_provider_mode=_env_value("VLA_PROVIDER_MODE", "blocked") or "blocked",
    vla_provider_endpoint=_env_value("VLA_PROVIDER_ENDPOINT"),
    vla_provider_api_key=_env_value("VLA_PROVIDER_API_KEY"),
    vla_provider_model=_env_value("VLA_PROVIDER_MODEL", "qwen3-vl-plus") or "qwen3-vl-plus",
    vla_provider_timeout_seconds=float(_env_value("VLA_PROVIDER_TIMEOUT_SECONDS", "8.0") or "8.0"),
    vla_provider_max_queue_size=int(_env_value("VLA_PROVIDER_MAX_QUEUE_SIZE", "8") or "8"),
    vla_provider_cache_ttl_seconds=float(_env_value("VLA_PROVIDER_CACHE_TTL_SECONDS", "30.0") or "30.0"),
    non_runtime_model_mode=_env_value("NON_RUNTIME_MODEL_MODE", "disabled") or "disabled",
    non_runtime_model_endpoint=_env_value("NON_RUNTIME_MODEL_ENDPOINT"),
    non_runtime_model_api_key=_env_value("NON_RUNTIME_MODEL_API_KEY"),
    non_runtime_model_model=_env_value("NON_RUNTIME_MODEL_MODEL", "doubao-seed-2.0-lite") or "doubao-seed-2.0-lite",
    non_runtime_model_timeout_seconds=float(_env_value("NON_RUNTIME_MODEL_TIMEOUT_SECONDS", "30.0") or "30.0"),
)
