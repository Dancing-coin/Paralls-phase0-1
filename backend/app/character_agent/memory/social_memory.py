from copy import deepcopy

from app.character_agent.models.social_memory import CharacterSocialMemoryRecord


class CharacterSocialMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def upsert_relation(
        self,
        actor_id: str,
        entity_id: str,
        trust_baseline: float,
        suspicion_baseline: float,
        intimacy: float,
        dependency: float,
        unresolved_tension: float,
        shared_secret_refs: list[str],
        source_event_id: str,
        producer_ts: int,
    ) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        entry = {
            "memory_id": f"social:{actor_id}:{entity_id}",
            "actor_id": actor_id,
            "entity_id": entity_id,
            "trust_baseline": trust_baseline,
            "suspicion_baseline": suspicion_baseline,
            "intimacy": intimacy,
            "dependency": dependency,
            "unresolved_tension": unresolved_tension,
            "shared_secret_refs": list(shared_secret_refs),
            "source_event_id": source_event_id,
            "producer_ts": producer_ts,
        }
        for idx, existing in enumerate(entries):
            if existing["entity_id"] == entity_id:
                entries[idx] = deepcopy(entry)
                return deepcopy(entries[idx])
        stored = deepcopy(entry)
        entries.append(stored)
        return deepcopy(stored)

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [deepcopy(entry) for entry in self._entries_by_actor.get(actor_id, [])]

    def recall_records(self, actor_id: str) -> list[CharacterSocialMemoryRecord]:
        return [CharacterSocialMemoryRecord(**deepcopy(entry)) for entry in self._entries_by_actor.get(actor_id, [])]
