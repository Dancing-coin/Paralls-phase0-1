from copy import deepcopy

from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState


class CharacterWorkingMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def remember_event(self, actor_id: str, event: dict[str, object]) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        stored = deepcopy(event)
        entries.append(stored)
        return deepcopy(stored)

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return deepcopy(self._entries_by_actor.get(actor_id, []))

    def build_state(self, actor_id: str, private_snapshot: dict[str, object] | None = None) -> CharacterWorkingMemoryState:
        entries = self.recall(actor_id)
        recent_perceived_events = [
            entry
            for entry in entries
            if str(entry.get("event_type", "") or "") in {"character_perceived_event", "self_body_perceived_event"}
        ]
        recent_esm_results = [
            entry
            for entry in entries
            if str(entry.get("event_type", "") or "") in {"character_agent_settlement_result", "character_agent_dialogue_response"}
        ]
        recent_siming_catalysts = [
            entry
            for entry in entries
            if str(entry.get("event_type", "") or "") == "siming_output_event"
        ]
        return CharacterWorkingMemoryState(
            recent_perceived_events=deepcopy(recent_perceived_events),
            recent_esm_results=deepcopy(recent_esm_results),
            recent_siming_catalysts=deepcopy(recent_siming_catalysts),
            private_snapshot=deepcopy(private_snapshot or {}),
        )
