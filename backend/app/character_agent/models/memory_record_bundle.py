from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.models.event_memory import CharacterEventMemoryRecord
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord
from app.character_agent.models.knowledge_memory import CharacterKnowledgeMemoryRecord
from app.character_agent.models.observation_memory import CharacterObservationMemoryRecord
from app.character_agent.models.social_memory import CharacterSocialMemoryRecord


class CharacterMemoryRecordBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_memories: list[CharacterEventMemoryRecord] = Field(default_factory=list)
    observation_memories: list[CharacterObservationMemoryRecord] = Field(default_factory=list)
    knowledge_memories: list[CharacterKnowledgeMemoryRecord] = Field(default_factory=list)
    social_memories: list[CharacterSocialMemoryRecord] = Field(default_factory=list)
    higher_order_memories: list[CharacterHigherOrderMemoryRecord] = Field(default_factory=list)
