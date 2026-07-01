from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorldEntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str
    zone_id: str | None = None


class WorldStateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: WorldEntityRef
    changed_fields: dict[str, object] = Field(default_factory=dict)
    producer_ts: int


class WorldRuntimeEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str
    scene_id: str
    zone_id: str
    facts: list[str] = Field(default_factory=list)
    deltas: list[WorldStateDelta] = Field(default_factory=list)
