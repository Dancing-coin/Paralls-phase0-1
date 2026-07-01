from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterEventMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    actor_id: str
    event_id: str
    source_event_id: str
    world_ts: int
    event_type: str
    summary: str
    clarity_score: float = Field(ge=0.0, le=1.0)
    certainty_score: float = Field(ge=0.0, le=1.0)
    refs: list[str] = Field(default_factory=list)

