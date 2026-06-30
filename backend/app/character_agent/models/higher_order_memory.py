from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterHigherOrderMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    actor_id: str
    subject_actor_id: str
    proposition_key: str
    meta_belief: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_event_id: str
    producer_ts: int


__all__ = ["CharacterHigherOrderMemoryRecord"]
