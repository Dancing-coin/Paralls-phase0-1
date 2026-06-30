from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterSocialMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    actor_id: str
    entity_id: str
    trust_baseline: float = Field(ge=0.0, le=1.0)
    suspicion_baseline: float = Field(ge=0.0, le=1.0)
    intimacy: float = Field(ge=0.0, le=1.0)
    dependency: float = Field(ge=0.0, le=1.0)
    unresolved_tension: float = Field(ge=0.0, le=1.0)
    shared_secret_refs: list[str] = Field(default_factory=list)
    source_event_id: str
    producer_ts: int
