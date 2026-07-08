from __future__ import annotations

import math
from collections.abc import Mapping

from app.character_agent.models.need_tension import NeedTensionDelta

ProfileMapping = Mapping[str, object]


class AffectEngine:
    def evaluate(
        self,
        *,
        effective_profile: ProfileMapping,
        need_delta: NeedTensionDelta,
    ) -> dict[str, dict[str, float]]:
        temperament_layer = self._mapping_or_empty(effective_profile.get("temperament_response_layer"))

        baseline_temperament = self._mapping_or_empty(temperament_layer.get("baseline_temperament"))

        raw_reactivity = baseline_temperament.get("emotional_reactivity")
        emotional_reactivity = self._safe_float(raw_reactivity, default=0.5)

        has_safety_pressure = need_delta.safety is not None
        has_esteem_pressure = need_delta.esteem is not None
        if not has_safety_pressure and not has_esteem_pressure:
            return {"dynamic_state_delta": {}}

        safety_pressure = self._safe_float(need_delta.safety, default=0.0)
        esteem_pressure = self._safe_float(need_delta.esteem, default=0.0)

        return {
            "dynamic_state_delta": {
                "vigilance_level": min(1.0, safety_pressure * emotional_reactivity),
                "stress_load": min(1.0, (safety_pressure + esteem_pressure) * 0.5),
                "affect_valence": max(-1.0, -1.0 * (safety_pressure + esteem_pressure)),
            }
        }

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


__all__ = ["AffectEngine"]
