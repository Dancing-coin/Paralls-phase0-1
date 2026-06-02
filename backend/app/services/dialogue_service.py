from app.config import settings


class DialogueService:
    def generate_reply(self, actor_id: str, content: str) -> tuple[str, str]:
        if settings.dialogue_mode == "stub":
            if "letter" in content.lower():
                return ("I saw something move near the desk.", "alert")
            if actor_id == "char_b":
                return ("I am watching the room.", "neutral")
            return ("I am here. What do you need?", "neutral")

        if "letter" in content.lower():
            return ("I saw something move near the desk.", "alert")
        return ("I am here. What do you need?", "neutral")
