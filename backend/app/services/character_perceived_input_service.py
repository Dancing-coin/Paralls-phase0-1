from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent


class CharacterPerceivedInputService:
    def __init__(self) -> None:
        self._latest_by_actor: dict[str, CharacterPerceivedEvent] = {}
        self._latest_self_body_by_actor: dict[str, SelfBodyPerceivedEvent] = {}

    def clear(self) -> None:
        self._latest_by_actor.clear()
        self._latest_self_body_by_actor.clear()

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

    def apply_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> dict[str, object]:
        self._latest_self_body_by_actor[event.actor_id] = event
        return {
            "actor_id": event.actor_id,
            "body_state_class": event.body_state_class,
            "perceived_summary": event.perceived_summary,
            "source_body_result_id": event.source_body_result_id,
        }

    def get_latest_self_body(self, actor_id: str) -> SelfBodyPerceivedEvent | None:
        return self._latest_self_body_by_actor.get(actor_id)
