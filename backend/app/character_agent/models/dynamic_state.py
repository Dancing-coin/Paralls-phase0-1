from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterDynamicState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    vigilance_level: float = Field(ge=0.0, le=1.0)
    distraction_level: float = Field(ge=0.0, le=1.0)
    stress_load: float = Field(ge=0.0, le=1.0)
    social_pressure: float = Field(ge=0.0, le=1.0)
    masking_pressure: float = Field(ge=0.0, le=1.0)
    affect_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    motivation_stack: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)


__all__ = ["CharacterDynamicState"]
