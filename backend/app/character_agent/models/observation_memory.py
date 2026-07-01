from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterObservationMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    actor_id: str
    source_event_id: str
    world_ts: int
    observed_entity_id: str
    observation_type: str
    observation_summary: str
    clarity_score: float = Field(ge=0.0, le=1.0)
    certainty_score: float = Field(ge=0.0, le=1.0)
    distortion_tags: list[str] = Field(default_factory=list)
    refs: list[str] = Field(default_factory=list)

