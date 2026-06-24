from copy import deepcopy


class CharacterObservationMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}
        self._ordinal_by_actor: dict[str, int] = {}

    def record_observation(
        self,
        actor_id: str,
        source_event_id: str,
        world_ts: int,
        observed_entity_id: str,
        observation_type: str,
        observation_summary: str,
        clarity_score: float,
        certainty_score: float,
        distortion_tags: list[str],
        refs: list[str],
    ) -> dict[str, object]:
        entries = self._entries_by_actor.setdefault(actor_id, [])
        ordinal = self._ordinal_by_actor.get(actor_id, 0) + 1
        self._ordinal_by_actor[actor_id] = ordinal
        entry = {
            "memory_id": f"observation:{actor_id}:{source_event_id}:{observed_entity_id}:{observation_type}:{ordinal}",
            "actor_id": actor_id,
            "source_event_id": source_event_id,
            "world_ts": world_ts,
            "observed_entity_id": observed_entity_id,
            "observation_type": observation_type,
            "observation_summary": observation_summary,
            "clarity_score": clarity_score,
            "certainty_score": certainty_score,
            "distortion_tags": list(distortion_tags),
            "refs": list(refs),
        }
        stored = deepcopy(entry)
        entries.append(stored)
        return deepcopy(stored)

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [deepcopy(entry) for entry in self._entries_by_actor.get(actor_id, [])]
