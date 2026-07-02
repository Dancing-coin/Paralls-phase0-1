import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


SimingLlmProviderName = Literal["disabled", "openai_responses", "deepseek_chat"]


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
    siming_llm_mode: Literal["disabled", "http"] = "disabled"
    siming_llm_api_key: str | None = Field(default=None, repr=False, exclude=True)
    siming_llm_endpoint: str = "https://api.openai.com/v1/responses"
    siming_llm_model: str = "gpt-5.4-mini"
    siming_llm_timeout_seconds: float = 8.0
    siming_llm_provider_order: list[SimingLlmProviderName] = Field(default_factory=lambda: ["openai_responses"])
    siming_llm_routes: list[SimingLlmRouteSettings] = Field(default_factory=list)


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


settings = Settings(
    dialogue_mode=_env_value("DIALOGUE_MODE", "stub") or "stub",
    tts_mode=_env_value("TTS_MODE", "stub") or "stub",
    siming_llm_mode=_env_value("SIMING_LLM_MODE", "disabled") or "disabled",
    siming_llm_api_key=_env_value("SIMING_LLM_API_KEY"),
    siming_llm_endpoint=_env_value("SIMING_LLM_ENDPOINT", "https://api.openai.com/v1/responses")
    or "https://api.openai.com/v1/responses",
    siming_llm_model=_env_value("SIMING_LLM_MODEL", "gpt-5.4-mini") or "gpt-5.4-mini",
    siming_llm_timeout_seconds=float(_env_value("SIMING_LLM_TIMEOUT_SECONDS", "8.0") or "8.0"),
    siming_llm_provider_order=_env_list("SIMING_LLM_PROVIDER_ORDER", ["openai_responses"]),
)
