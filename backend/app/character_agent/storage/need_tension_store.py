from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.need_tension import NeedTensionDelta, NeedTensionState


class CharacterNeedTensionStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, dict[str, object]] = {}

    def write(self, actor_id: str, state: dict[str, object] | NeedTensionState) -> None:
        payload = self._payload(actor_id, state)
        self._by_actor[actor_id] = NeedTensionState(**payload).model_dump()

    def read(self, actor_id: str) -> dict[str, object]:
        stored = self._by_actor.get(actor_id)
        if stored is None:
            return self._default_state(actor_id)
        return deepcopy(stored)

    def read_record(self, actor_id: str) -> NeedTensionState:
        return NeedTensionState(**self.read(actor_id))

    def merge_delta(self, actor_id: str, delta: dict[str, object] | NeedTensionDelta) -> dict[str, object]:
        current = self.read(actor_id)
        delta_payload = delta.as_mapping() if isinstance(delta, NeedTensionDelta) else deepcopy(delta)
        payload = {**current, **delta_payload, "actor_id": actor_id}
        normalized = NeedTensionState(**payload).model_dump()
        self._by_actor[actor_id] = normalized
        return deepcopy(normalized)

    def _default_state(self, actor_id: str) -> dict[str, object]:
        return NeedTensionState(actor_id=actor_id).model_dump()

    def _payload(self, actor_id: str, state: dict[str, object] | NeedTensionState) -> dict[str, object]:
        if isinstance(state, NeedTensionState):
            payload = state.model_dump()
        else:
            payload = deepcopy(state)
        return {"actor_id": actor_id, **payload}


__all__ = ["CharacterNeedTensionStore"]
