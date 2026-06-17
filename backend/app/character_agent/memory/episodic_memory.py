class CharacterEpisodicMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def remember(
        self,
        actor_id: str,
        summary: str,
        tags: list[str],
        source_event_id: str,
        producer_ts: int,
    ) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        entry = {
            "memory_id": f"episode:{actor_id}:{producer_ts}:{len(entries) + 1}",
            "actor_id": actor_id,
            "summary": summary,
            "tags": list(tags),
            "source_event_id": source_event_id,
            "producer_ts": producer_ts,
        }
        entries.append(entry)
        return entry

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [dict(entry) for entry in self._entries_by_actor.get(actor_id, [])]
