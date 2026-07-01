from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.goal_runtime import CharacterGoalStateRecord


class CharacterGoalStateStore:
    _HISTORY_LIMIT = 8

    def __init__(self) -> None:
        self._by_actor: dict[str, CharacterGoalStateRecord] = {}
        self._previous_by_actor: dict[str, CharacterGoalStateRecord] = {}
        self._history_by_actor: dict[str, list[CharacterGoalStateRecord]] = {}

    def write(self, actor_id: str, state: dict[str, object] | CharacterGoalStateRecord) -> None:
        current = self._by_actor.get(actor_id)
        if current is not None:
            self._previous_by_actor[actor_id] = current.model_copy(deep=True)
        normalized = self._coerce_record(actor_id, state)
        self._by_actor[actor_id] = normalized
        history = self._history_by_actor.setdefault(actor_id, [])
        history.append(normalized.model_copy(deep=True))
        self._history_by_actor[actor_id] = history[-self._HISTORY_LIMIT :]

    def read(self, actor_id: str) -> dict[str, object]:
        record = self._by_actor.get(actor_id)
        return record.model_dump() if record is not None else {}

    def previous(self, actor_id: str) -> dict[str, object]:
        record = self._previous_by_actor.get(actor_id)
        return record.model_dump() if record is not None else {}

    def history(self, actor_id: str) -> list[dict[str, object]]:
        return [record.model_dump() for record in self._history_by_actor.get(actor_id, [])]

    def read_record(self, actor_id: str) -> CharacterGoalStateRecord | None:
        record = self._by_actor.get(actor_id)
        return record.model_copy(deep=True) if record is not None else None

    def previous_record(self, actor_id: str) -> CharacterGoalStateRecord | None:
        record = self._previous_by_actor.get(actor_id)
        return record.model_copy(deep=True) if record is not None else None

    def history_records(self, actor_id: str) -> list[CharacterGoalStateRecord]:
        return [record.model_copy(deep=True) for record in self._history_by_actor.get(actor_id, [])]

    def _coerce_record(
        self,
        actor_id: str,
        state: dict[str, object] | CharacterGoalStateRecord,
    ) -> CharacterGoalStateRecord:
        if isinstance(state, CharacterGoalStateRecord):
            if state.actor_id == actor_id:
                return state.model_copy(deep=True)
            payload = state.model_dump()
            payload["actor_id"] = actor_id
            return CharacterGoalStateRecord(**payload)
        payload = dict(state)
        payload.setdefault("actor_id", actor_id)
        return CharacterGoalStateRecord(**payload)


__all__ = ["CharacterGoalStateStore"]
