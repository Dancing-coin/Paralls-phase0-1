from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.dynamic_state import CharacterDynamicState


class CharacterDynamicStateStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, dict[str, object]] = {}

    def write(self, actor_id: str, state: dict[str, object]) -> None:
        payload = {"actor_id": actor_id, **deepcopy(state)}
        self._by_actor[actor_id] = CharacterDynamicState(**payload).model_dump()

    def read(self, actor_id: str) -> dict[str, object]:
        stored = self._by_actor.get(actor_id)
        if stored is None:
            return self._default_state(actor_id)
        return deepcopy(stored)

    def read_record(self, actor_id: str) -> CharacterDynamicState:
        return CharacterDynamicState(**self.read(actor_id))

    def merge_delta(self, actor_id: str, delta: dict[str, object]) -> dict[str, object]:
        current = self.read(actor_id)
        payload = {**current, **deepcopy(delta), "actor_id": actor_id}
        normalized = CharacterDynamicState(**payload).model_dump()
        self._by_actor[actor_id] = normalized
        return deepcopy(normalized)

    def _default_state(self, actor_id: str) -> dict[str, object]:
        return CharacterDynamicState(
            actor_id=actor_id,
            vigilance_level=0.0,
            distraction_level=0.0,
            stress_load=0.0,
            social_pressure=0.0,
            masking_pressure=0.0,
        ).model_dump()


__all__ = ["CharacterDynamicStateStore"]
