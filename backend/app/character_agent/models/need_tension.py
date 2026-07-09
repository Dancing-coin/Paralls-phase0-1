from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


RuntimeScalar = float


class StrictRuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NeedTensionState(StrictRuntimeModel):
    actor_id: str
    physiological_pressure: RuntimeScalar = Field(default=0.0, ge=0.0, le=1.0)
    safety_pressure: RuntimeScalar = Field(default=0.0, ge=0.0, le=1.0)
    belonging_pressure: RuntimeScalar = Field(default=0.0, ge=0.0, le=1.0)
    esteem_pressure: RuntimeScalar = Field(default=0.0, ge=0.0, le=1.0)
    self_actualization_pressure: RuntimeScalar = Field(default=0.0, ge=0.0, le=1.0)
    recent_satisfaction: dict[str, float] = Field(default_factory=dict)
    dominant_need: str = ""
    secondary_need: str = ""
    motivation_stack: list[str] = Field(default_factory=list)
    pressure_sources: list[str] = Field(default_factory=list)


class NeedTensionDelta(StrictRuntimeModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    physiological_pressure: RuntimeScalar | None = Field(default=None, alias="physiological", ge=0.0, le=1.0)
    safety_pressure: RuntimeScalar | None = Field(default=None, alias="safety", ge=0.0, le=1.0)
    belonging_pressure: RuntimeScalar | None = Field(default=None, alias="belonging", ge=0.0, le=1.0)
    esteem_pressure: RuntimeScalar | None = Field(default=None, alias="esteem", ge=0.0, le=1.0)
    self_actualization_pressure: RuntimeScalar | None = Field(
        default=None,
        alias="self_actualization",
        ge=0.0,
        le=1.0,
    )
    dominant_need: str | None = None
    secondary_need: str | None = None
    motivation_stack: list[str] | None = None
    pressure_sources: list[str] | None = None
    recent_satisfaction: dict[str, float] | None = None

    @property
    def physiological(self) -> RuntimeScalar | None:
        return self.physiological_pressure

    @property
    def safety(self) -> RuntimeScalar | None:
        return self.safety_pressure

    @property
    def belonging(self) -> RuntimeScalar | None:
        return self.belonging_pressure

    @property
    def esteem(self) -> RuntimeScalar | None:
        return self.esteem_pressure

    @property
    def self_actualization(self) -> RuntimeScalar | None:
        return self.self_actualization_pressure

    def as_mapping(self) -> dict[str, object]:
        payload = self.model_dump(by_alias=False)
        mapping: dict[str, object] = {}
        for key, value in payload.items():
            if value is None:
                continue
            if key.endswith("_pressure"):
                mapping[key] = float(value)
                continue
            if key == "pressure_sources":
                mapping[key] = list(value)
                continue
            if key == "recent_satisfaction":
                mapping[key] = dict(value)
                continue
            mapping[key] = value
        return mapping


__all__ = ["NeedTensionDelta", "NeedTensionState"]
