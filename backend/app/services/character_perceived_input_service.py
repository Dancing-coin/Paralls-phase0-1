from app.models.character_perceived import CharacterPerceivedEvent


class CharacterPerceivedInputService:
    def __init__(self) -> None:
        self._latest_by_actor: dict[str, CharacterPerceivedEvent] = {}

    def clear(self) -> None:
        self._latest_by_actor.clear()

    def apply_character_perceived_event(self, event: CharacterPerceivedEvent) -> dict[str, object]:
        self._latest_by_actor[event.actor_id] = event
        return {
            "actor_id": event.actor_id,
            "percept_channel": event.percept_channel,
            "perceived_summary": event.perceived_summary,
            "source_candidate_event_id": event.source_candidate_event_id,
        }

    def get_latest(self, actor_id: str) -> CharacterPerceivedEvent | None:
        return self._latest_by_actor.get(actor_id)
