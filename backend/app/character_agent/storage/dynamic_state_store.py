from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.dynamic_state import AffectState, CharacterDynamicState


_AFFECT_DELTA_KEYS = frozenset(AffectState.model_fields)


class CharacterDynamicStateStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, dict[str, object]] = {}

    def write(self, actor_id: str, state: dict[str, object]) -> None:
        payload = {"actor_id": actor_id, **deepcopy(state)}
        self._by_actor[actor_id] = CharacterDynamicState(**payload).storage_dump()

    def read(self, actor_id: str) -> dict[str, object]:
        stored = self._stored_state(actor_id)
        if stored is None:
            return self._default_state(actor_id)
        return CharacterDynamicState(**stored).legacy_flat_dump()

    def read_record(self, actor_id: str) -> CharacterDynamicState:
        stored = self._stored_state(actor_id)
        if stored is None:
            return CharacterDynamicState(**self._default_state(actor_id))
        return CharacterDynamicState(**deepcopy(stored))

    def merge_delta(self, actor_id: str, delta: dict[str, object]) -> dict[str, object]:
        current = self._stored_state(actor_id) or self._default_state(actor_id)
        normalized_delta = self._group_flat_affect_delta(deepcopy(delta))
        payload = self._merge_mapping(current, normalized_delta)
        self._apply_grouped_legacy_overrides(payload, delta)
        payload["actor_id"] = actor_id
        normalized = CharacterDynamicState(**payload)
        self._by_actor[actor_id] = normalized.storage_dump()
        return normalized.legacy_flat_dump()

    def _default_state(self, actor_id: str) -> dict[str, object]:
        return CharacterDynamicState(
            actor_id=actor_id,
            vigilance_level=0.0,
            distraction_level=0.0,
            stress_load=0.0,
            social_pressure=0.0,
            masking_pressure=0.0,
        ).legacy_flat_dump()

    def _stored_state(self, actor_id: str) -> dict[str, object] | None:
        stored = self._by_actor.get(actor_id)
        return deepcopy(stored) if stored is not None else None

    def _merge_mapping(self, current: dict[str, object], delta: dict[str, object]) -> dict[str, object]:
        merged = deepcopy(current)
        for key, value in delta.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_mapping(
                    merged.get(key, {}),
                    value,
                )
                continue
            merged[key] = value
        return merged

    def _apply_grouped_legacy_overrides(self, payload: dict[str, object], delta: dict[str, object]) -> None:
        tension_delta = delta.get("tension_state")
        if isinstance(tension_delta, dict):
            tension_payload = payload.get("tension_state")
            if isinstance(tension_payload, dict):
                for key in ("stress_load", "social_pressure", "masking_pressure"):
                    if key in delta:
                        continue
                    if key in tension_delta:
                        payload[key] = tension_payload.get(key)

        motivation_delta = delta.get("motivation_state")
        if isinstance(motivation_delta, dict):
            motivation_payload = payload.get("motivation_state")
            if isinstance(motivation_payload, dict):
                for key in ("motivation_stack", "unresolved_conflicts"):
                    if key in delta:
                        continue
                    if key in motivation_delta:
                        payload[key] = deepcopy(motivation_payload.get(key))

    def _group_flat_affect_delta(self, delta: dict[str, object]) -> dict[str, object]:
        affect_delta: dict[str, object] = {}
        for key in list(delta):
            if key not in _AFFECT_DELTA_KEYS:
                continue
            affect_delta[key] = delta.pop(key)
        if not affect_delta:
            return delta
        existing = delta.get("affect_state")
        if not isinstance(existing, dict):
            existing = {}
        delta["affect_state"] = self._merge_mapping(existing, affect_delta)
        return delta


__all__ = ["CharacterDynamicStateStore"]
