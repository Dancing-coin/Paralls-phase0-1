from __future__ import annotations

from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle
from app.character_agent.models.working_memory_state import CharacterWorkingMemoryState
from app.character_agent.storage.memory_store import CharacterMemoryStorePort


class CharacterMemoryStoreRouter:
    def __init__(
        self,
        *,
        light_store: CharacterMemoryStorePort,
        graph_store: CharacterMemoryStorePort,
        heavy_actor_ids: frozenset[str],
    ) -> None:
        self._light = light_store
        self._graph = graph_store
        self._heavy_actor_ids = heavy_actor_ids

    def _store_for(self, actor_id: str) -> CharacterMemoryStorePort:
        return self._graph if actor_id in self._heavy_actor_ids else self._light

    def write_event(self, event: dict[str, object]) -> None:
        self._store_for(str(event.get("actor_id", "") or "")).write_event(event)

    def retrieval_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
        return self._store_for(actor_id).retrieval_bundle(actor_id)

    def retrieval_record_bundle(
        self,
        actor_id: str,
        *,
        story_branch_id: str | None = None,
        valid_at: int | None = None,
    ) -> CharacterMemoryRecordBundle:
        return self._store_for(actor_id).retrieval_record_bundle(
            actor_id,
            story_branch_id=story_branch_id,
            valid_at=valid_at,
        )

    def working_memory_state(
        self,
        actor_id: str,
        private_snapshot: dict[str, object] | None = None,
        dynamic_state: dict[str, object] | CharacterDynamicState | None = None,
    ) -> CharacterWorkingMemoryState:
        return self._store_for(actor_id).working_memory_state(
            actor_id,
            private_snapshot=private_snapshot,
            dynamic_state=dynamic_state,
        )
