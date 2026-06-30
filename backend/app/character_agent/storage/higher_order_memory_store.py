from __future__ import annotations

from copy import deepcopy


class CharacterHigherOrderMemoryStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, list[dict[str, object]]] = {}

    def append(self, actor_id: str, record: dict[str, object]) -> None:
        self._by_actor.setdefault(actor_id, []).append(deepcopy(record))

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return deepcopy(self._by_actor.get(actor_id, []))


__all__ = ["CharacterHigherOrderMemoryStore"]
