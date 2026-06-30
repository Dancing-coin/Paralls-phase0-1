from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterBeliefDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposition_key: str
    proposition: str = ""
    state: str = "suspected"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CharacterSocialDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    trust_baseline: float = Field(default=0.5, ge=0.0, le=1.0)
    suspicion_baseline: float = Field(default=0.0, ge=0.0, le=1.0)
    intimacy: float = Field(default=0.0, ge=0.0, le=1.0)
    dependency: float = Field(default=0.0, ge=0.0, le=1.0)
    unresolved_tension: float = Field(default=0.0, ge=0.0, le=1.0)
    shared_secret_refs: list[str] = Field(default_factory=list)


class CharacterHigherOrderDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject_actor_id: str
    proposition_key: str = ""
    meta_belief: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CharacterDynamicStateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vigilance_level: float | None = Field(default=None, ge=0.0, le=1.0)
    distraction_level: float | None = Field(default=None, ge=0.0, le=1.0)
    stress_load: float | None = Field(default=None, ge=0.0, le=1.0)
    social_pressure: float | None = Field(default=None, ge=0.0, le=1.0)
    masking_pressure: float | None = Field(default=None, ge=0.0, le=1.0)

    def as_mapping(self) -> dict[str, float]:
        payload = self.model_dump()
        return {
            str(key): float(value)
            for key, value in payload.items()
            if isinstance(value, (int, float))
        }
