from __future__ import annotations

import math
from collections.abc import Mapping

from app.character_agent.models.need_tension import NeedTensionDelta

ProfileMapping = Mapping[str, object]

TAG_TO_NEEDS = {
    "spatial_uncertainty": ["safety"],
    "public_dismissal": ["esteem"],
    "goal_blocked": ["esteem", "self_actualization"],
    "social_isolation": ["belonging"],
    "resource_scarcity": ["physiological"],
}


class NeedTensionEngine:
    def evaluate(
        self,
        *,
        effective_profile: ProfileMapping,
        event: ProfileMapping,
    ) -> NeedTensionDelta:
        tags = self._sorted_tags(event.get("event_tags", []))
        need_layer = self._mapping_or_empty(effective_profile.get("need_hierarchy_layer"))

        weight_map = need_layer.get("effective_weights")
        if not isinstance(weight_map, Mapping):
            weight_map = need_layer.get("base_weights", {})
        weight_map = self._mapping_or_empty(weight_map)

        sensitivity_map = self._mapping_or_empty(need_layer.get("deprivation_sensitivity"))

        pressure_by_need: dict[str, float] = {}
        for tag in tags:
            for need_key in TAG_TO_NEEDS.get(tag, []):
                pressure = self._pressure(weight_map, sensitivity_map, need_key)
                pressure_by_need[need_key] = max(pressure_by_need.get(need_key, 0.0), pressure)

        return NeedTensionDelta(
            physiological=pressure_by_need.get("physiological"),
            safety=pressure_by_need.get("safety"),
            belonging=pressure_by_need.get("belonging"),
            esteem=pressure_by_need.get("esteem"),
            self_actualization=pressure_by_need.get("self_actualization"),
            pressure_sources=tags,
        )

    @staticmethod
    def _pressure(
        weights: ProfileMapping,
        sensitivities: ProfileMapping,
        need_key: str,
    ) -> float:
        weight = NeedTensionEngine._safe_float(weights.get(need_key), default=0.0)
        sensitivity = NeedTensionEngine._safe_float(sensitivities.get(need_key), default=0.0)
        return weight * sensitivity * 0.25

    @staticmethod
    def _safe_float(value: object, *, default: float) -> float:
        if isinstance(value, bool) or value is None or not isinstance(value, int | float | str):
            return default
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(parsed):
            return default
        return max(0.0, min(1.0, parsed))

    @staticmethod
    def _mapping_or_empty(value: object) -> ProfileMapping:
        if isinstance(value, Mapping):
            return value
        return {}

    @staticmethod
    def _sorted_tags(raw_tags: object) -> list[str]:
        if isinstance(raw_tags, list | tuple | set):
            return sorted({str(tag) for tag in raw_tags})
        if raw_tags in (None, ""):
            return []
        return [str(raw_tags)]


__all__ = ["NeedTensionEngine", "TAG_TO_NEEDS"]
