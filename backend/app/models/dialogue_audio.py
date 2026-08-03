from typing import Literal

from pydantic import BaseModel, Field


class DialogueAudio(BaseModel):
    """Presentation-only audio attached to a dialogue response."""

    contract: Literal["tts_audio.v1"] = "tts_audio.v1"
    mode: Literal["stub", "clip"]
    status: Literal["stub", "ready", "fallback"]
    provider: str
    voice_id: str
    content_type: str | None = None
    encoding: Literal["base64"] | None = None
    payload: str | None = None
    sample_rate_hz: int | None = Field(default=None, ge=1)
    channels: int | None = Field(default=None, ge=1)
    sample_format: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    sequence: int = Field(default=0, ge=0)
    is_final: bool = True
    fallback_reason: str | None = None
