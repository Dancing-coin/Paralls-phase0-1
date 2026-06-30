from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord


class CharacterHigherOrderMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def append(self, *, actor_id: str, record: dict[str, object]) -> None:
        self._entries_by_actor.setdefault(actor_id, []).append(deepcopy(record))

    def upsert_meta_belief(
        self,
        *,
        actor_id: str,
        subject_actor_id: str,
        proposition_key: str,
        meta_belief: str,
        confidence: float,
        source_event_id: str,
        producer_ts: int,
    ) -> dict[str, object]:
        entry = {
            "memory_id": source_event_id or f"higher_order:{actor_id}:{subject_actor_id}:{producer_ts}",
            "actor_id": actor_id,
            "subject_actor_id": subject_actor_id,
            "proposition_key": proposition_key,
            "meta_belief": meta_belief,
            "confidence": confidence,
            "source_event_id": source_event_id,
            "producer_ts": producer_ts,
        }
        entries = self._entries_by_actor.setdefault(actor_id, [])
        for index, existing in enumerate(entries):
            if (
                str(existing.get("subject_actor_id", "") or "") == subject_actor_id
                and str(existing.get("proposition_key", "") or "") == proposition_key
            ):
                entries[index] = deepcopy(entry)
                return deepcopy(entry)
        entries.append(deepcopy(entry))
        return deepcopy(entry)

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return deepcopy(self._entries_by_actor.get(actor_id, []))

    def recall_records(self, actor_id: str) -> list[CharacterHigherOrderMemoryRecord]:
        return [CharacterHigherOrderMemoryRecord(**deepcopy(entry)) for entry in self._entries_by_actor.get(actor_id, [])]
