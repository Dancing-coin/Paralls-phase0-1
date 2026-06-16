from typing import Literal

from pydantic import BaseModel, Field


SimingLlmProviderName = Literal["disabled", "openai_responses"]


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


settings = Settings()
