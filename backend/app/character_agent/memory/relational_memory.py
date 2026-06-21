class CharacterRelationalMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def upsert_belief(
        self,
        actor_id: str,
        entity_id: str,
        belief_type: str,
        value: str,
        source_event_id: str,
        producer_ts: int,
    ) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        entry = {
            "memory_id": f"relation:{actor_id}:{entity_id}:{belief_type}",
            "actor_id": actor_id,
            "entity_id": entity_id,
            "belief_type": belief_type,
            "value": value,
            "source_event_id": source_event_id,
            "producer_ts": producer_ts,
        }
        for idx, existing in enumerate(entries):
            if (
                existing["entity_id"] == entity_id
                and existing["belief_type"] == belief_type
            ):
                entries[idx] = entry
                return entry
        entries.append(entry)
        return entry

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [dict(entry) for entry in self._entries_by_actor.get(actor_id, [])]
