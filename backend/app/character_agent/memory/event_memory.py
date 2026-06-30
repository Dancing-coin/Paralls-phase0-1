from copy import deepcopy

from app.character_agent.models.event_memory import CharacterEventMemoryRecord


class CharacterEventMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}
        self._ordinal_by_actor: dict[str, int] = {}

    def record_event(
        self,
        actor_id: str,
        source_event_id: str,
        world_ts: int,
        event_type: str,
        summary: str,
        clarity_score: float,
        certainty_score: float,
        refs: list[str],
        event_id: str | None = None,
    ) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        ordinal = self._ordinal_by_actor.get(actor_id, 0) + 1
        self._ordinal_by_actor[actor_id] = ordinal
        event_key = event_id or source_event_id
        entry = {
            "memory_id": f"event:{actor_id}:{event_key}:{ordinal}",
            "actor_id": actor_id,
            "event_id": event_id or source_event_id,
            "source_event_id": source_event_id,
            "world_ts": world_ts,
            "event_type": event_type,
            "summary": summary,
            "clarity_score": clarity_score,
            "certainty_score": certainty_score,
            "refs": list(refs),
        }
        stored = deepcopy(entry)
        entries.append(stored)
        return deepcopy(stored)

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [deepcopy(entry) for entry in self._entries_by_actor.get(actor_id, [])]

    def recall_records(self, actor_id: str) -> list[CharacterEventMemoryRecord]:
        return [CharacterEventMemoryRecord(**deepcopy(entry)) for entry in self._entries_by_actor.get(actor_id, [])]
