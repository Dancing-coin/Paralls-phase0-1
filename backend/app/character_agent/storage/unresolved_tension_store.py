from __future__ import annotations

from app.character_agent.models.supervision import CharacterUnresolvedTension


class CharacterUnresolvedTensionStore:
    _HISTORY_LIMIT = 8

    def __init__(self) -> None:
        self._by_actor: dict[str, list[CharacterUnresolvedTension]] = {}

    def upsert(self, actor_id: str, tension: dict[str, object] | CharacterUnresolvedTension) -> None:
        normalized = self._model(tension)
        tensions = list(self._by_actor.get(actor_id, []))
        replaced = False
        for index, existing in enumerate(tensions):
            if existing.tension_id != normalized.tension_id:
                continue
            tensions[index] = normalized
            replaced = True
            break
        if not replaced:
            tensions.append(normalized)
        tensions.sort(key=lambda item: float(item.priority), reverse=True)
        self._by_actor[actor_id] = tensions[: self._HISTORY_LIMIT]

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return [item.model_dump() for item in self._by_actor.get(actor_id, [])]

    def recall_records(self, actor_id: str) -> list[CharacterUnresolvedTension]:
        return [item.model_copy(deep=True) for item in self._by_actor.get(actor_id, [])]

    def clear(self, actor_id: str) -> None:
        self._by_actor.pop(actor_id, None)

    def _model(self, value: dict[str, object] | CharacterUnresolvedTension) -> CharacterUnresolvedTension:
        if isinstance(value, CharacterUnresolvedTension):
            return value.model_copy(deep=True)
        return CharacterUnresolvedTension(**dict(value))


__all__ = ["CharacterUnresolvedTensionStore"]

