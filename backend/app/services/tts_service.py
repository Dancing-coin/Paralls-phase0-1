from app.config import settings


class TTSService:
    def synthesize(self, actor_id: str, content: str) -> dict[str, str]:
        if settings.tts_mode == "stub":
            return {
                "audio_mode": "stub",
                "audio_payload": f"stub://{actor_id}/{content}",
            }

        return {
            "audio_mode": settings.tts_mode,
            "audio_payload": content,
        }
