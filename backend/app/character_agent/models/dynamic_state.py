from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AffectState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fear: float = Field(default=0.0, ge=0.0, le=1.0)
    anger: float = Field(default=0.0, ge=0.0, le=1.0)
    shame: float = Field(default=0.0, ge=0.0, le=1.0)
    sadness: float = Field(default=0.0, ge=0.0, le=1.0)
    relief: float = Field(default=0.0, ge=0.0, le=1.0)
    curiosity: float = Field(default=0.0, ge=0.0, le=1.0)
    affection: float = Field(default=0.0, ge=0.0, le=1.0)


class TensionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stress_load: float = Field(default=0.0, ge=0.0, le=1.0)
    social_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    masking_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    chronic_safety_tension: float = Field(default=0.0, ge=0.0, le=1.0)
    belonging_frustration: float = Field(default=0.0, ge=0.0, le=1.0)
    esteem_wound_load: float = Field(default=0.0, ge=0.0, le=1.0)
    relationship_fatigue: float = Field(default=0.0, ge=0.0, le=1.0)


class MotivationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dominant_need: str = ""
    secondary_need: str = ""
    motivation_stack: list[str] = Field(default_factory=list)
    active_need_pressures: dict[str, float] = Field(default_factory=dict)
    unresolved_conflicts: list[str] = Field(default_factory=list)


class CharacterDynamicState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    vigilance_level: float = Field(ge=0.0, le=1.0)
    distraction_level: float = Field(ge=0.0, le=1.0)
    stress_load: float = Field(default=0.0, ge=0.0, le=1.0)
    social_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    masking_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
    affect_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    motivation_stack: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
    affect_state: AffectState = Field(default_factory=AffectState)
    tension_state: TensionState = Field(default_factory=TensionState)
    motivation_state: MotivationState = Field(default_factory=MotivationState)

    @model_validator(mode="before")
    @classmethod
    def _sync_grouped_and_legacy_inputs(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)

        tension_state = cls._mapping_value(payload.get("tension_state"))
        if isinstance(tension_state, dict):
            payload["tension_state"] = tension_state
            for key in ("stress_load", "social_pressure", "masking_pressure"):
                if key not in payload and key in tension_state:
                    payload[key] = tension_state[key]

        motivation_state = cls._mapping_value(payload.get("motivation_state"))
        if isinstance(motivation_state, dict):
            payload["motivation_state"] = motivation_state
            for key in ("motivation_stack", "unresolved_conflicts"):
                if key not in payload and key in motivation_state:
                    payload[key] = motivation_state[key]

        affect_state = cls._mapping_value(payload.get("affect_state"))
        if isinstance(affect_state, dict):
            payload["affect_state"] = affect_state

        if not isinstance(payload.get("tension_state"), dict):
            payload["tension_state"] = {
                "stress_load": payload.get("stress_load", 0.0),
                "social_pressure": payload.get("social_pressure", 0.0),
                "masking_pressure": payload.get("masking_pressure", 0.0),
            }
        else:
            normalized_tension = dict(payload["tension_state"])
            for key in ("stress_load", "social_pressure", "masking_pressure"):
                if key in payload:
                    normalized_tension[key] = payload[key]
                else:
                    normalized_tension.setdefault(key, 0.0)
            payload["tension_state"] = normalized_tension

        if not isinstance(payload.get("motivation_state"), dict):
            payload["motivation_state"] = {
                "motivation_stack": payload.get("motivation_stack", []),
                "unresolved_conflicts": payload.get("unresolved_conflicts", []),
            }
        else:
            normalized_motivation = dict(payload["motivation_state"])
            for key, default in (
                ("motivation_stack", []),
                ("unresolved_conflicts", []),
            ):
                if key in payload:
                    normalized_motivation[key] = payload[key]
                else:
                    normalized_motivation.setdefault(key, default)
            payload["motivation_state"] = normalized_motivation

        payload.setdefault("affect_state", {})
        return payload

    @model_validator(mode="after")
    def _sync_legacy_fields(self) -> "CharacterDynamicState":
        self.stress_load = self.tension_state.stress_load
        self.social_pressure = self.tension_state.social_pressure
        self.masking_pressure = self.tension_state.masking_pressure
        self.motivation_stack = list(self.motivation_state.motivation_stack)
        self.unresolved_conflicts = list(self.motivation_state.unresolved_conflicts)
        return self

    def storage_dump(self) -> dict[str, Any]:
        return super().model_dump()

    def legacy_flat_dump(self) -> dict[str, Any]:
        payload = self.storage_dump()
        payload.pop("affect_state", None)
        payload.pop("tension_state", None)
        payload.pop("motivation_state", None)
        return payload

    @staticmethod
    def _mapping_value(value: Any) -> dict[str, Any] | None:
        if isinstance(value, BaseModel):
            dumped = value.model_dump()
            if isinstance(dumped, dict):
                return dumped
        if isinstance(value, dict):
            return dict(value)
        return None


__all__ = ["AffectState", "CharacterDynamicState", "MotivationState", "TensionState"]
