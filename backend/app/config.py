from typing import Literal

from pydantic import BaseModel


class Settings(BaseModel):
    dialogue_mode: str = "stub"
    tts_mode: str = "stub"
    siming_llm_mode: Literal["disabled", "http"] = "disabled"
    siming_llm_api_key: str | None = None
    siming_llm_endpoint: str = "https://api.openai.com/v1/responses"
    siming_llm_model: str = "gpt-5.4-mini"
    siming_llm_timeout_seconds: float = 8.0


settings = Settings()
