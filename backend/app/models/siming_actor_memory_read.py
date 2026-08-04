from __future__ import annotations

from hashlib import sha256
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.models.memory_record_bundle import CharacterMemoryRecordBundle


class ActorMemoryRevisionVector(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event: str = ""
    observation: str = ""
    knowledge: str = ""
    social: str = ""
    higher_order: str = ""

    @classmethod
    def from_bundle(
        cls, bundle: CharacterMemoryRecordBundle
    ) -> "ActorMemoryRevisionVector":
        return cls(
            event=_pool_hash(bundle.event_memories),
            observation=_pool_hash(bundle.observation_memories),
            knowledge=_pool_hash(bundle.knowledge_memories),
            social=_pool_hash(bundle.social_memories),
            higher_order=_pool_hash(bundle.higher_order_memories),
        )


class ActorMemoryReadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    story_branch_id: str
    valid_at: int = Field(ge=0)
    expected_revision_vector: ActorMemoryRevisionVector | None = None


class ActorMemoryReadResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    story_branch_id: str
    valid_at: int
    revision_vector: ActorMemoryRevisionVector
    completeness: Literal["complete", "memory_surface_incomplete"]
    reason: str = ""
    bundle: CharacterMemoryRecordBundle


def _pool_hash(records: list[BaseModel]) -> str:
    if not records:
        return ""
    payload = [record.model_dump(mode="json") for record in records]
    payload.sort(key=lambda item: str(item["memory_id"]))
    return sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
