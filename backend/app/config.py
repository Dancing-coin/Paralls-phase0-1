import os

from pydantic import BaseModel


class Settings(BaseModel):
    dialogue_mode: str = "stub"
    tts_mode: str = "stub"


settings = Settings(
    dialogue_mode=os.getenv("DIALOGUE_MODE", "stub"),
    tts_mode=os.getenv("TTS_MODE", "stub"),
)
