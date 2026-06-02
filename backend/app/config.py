from pydantic import BaseModel


class Settings(BaseModel):
    dialogue_mode: str = "stub"
    tts_mode: str = "stub"


settings = Settings()
