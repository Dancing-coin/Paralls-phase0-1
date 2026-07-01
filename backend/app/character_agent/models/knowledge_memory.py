from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterKnowledgeMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    actor_id: str
    proposition_key: str
    proposition: str
    state: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_event_id: str
    producer_ts: int

