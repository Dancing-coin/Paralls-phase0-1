from copy import deepcopy

from app.character_agent.models.knowledge_state import KnowledgeState


class CharacterKnowledgeMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def upsert_proposition(
        self,
        actor_id: str,
        proposition_key: str,
        proposition: str,
        state: KnowledgeState | str,
        confidence: float,
        source_event_id: str,
        producer_ts: int,
    ) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        state_value = self._normalize_state(state)
        entry = {
            "memory_id": f"knowledge:{actor_id}:{proposition_key}",
            "actor_id": actor_id,
            "proposition_key": proposition_key,
            "proposition": proposition,
            "state": state_value,
            "confidence": confidence,
            "source_event_id": source_event_id,
            "producer_ts": producer_ts,
        }
        for idx, existing in enumerate(entries):
            if existing["proposition_key"] == proposition_key:
                entries[idx] = deepcopy(entry)
                return deepcopy(entries[idx])
        stored = deepcopy(entry)
        entries.append(stored)
        return deepcopy(stored)

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [deepcopy(entry) for entry in self._entries_by_actor.get(actor_id, [])]

    def _normalize_state(self, state: KnowledgeState | str) -> str:
        if isinstance(state, KnowledgeState):
            return state.value
        if state in KnowledgeState.__members__:
            return KnowledgeState[state].value
        return KnowledgeState(state).value
