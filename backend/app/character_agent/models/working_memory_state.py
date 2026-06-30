from __future__ import annotations

from pydantic import BaseModel, Field

from app.character_agent.models.dynamic_state import CharacterDynamicState


class CharacterWorkingMemoryState(BaseModel):
    recent_perceived_events: list[dict[str, object]] = Field(default_factory=list)
    recent_esm_results: list[dict[str, object]] = Field(default_factory=list)
    recent_siming_catalysts: list[dict[str, object]] = Field(default_factory=list)
    private_snapshot: dict[str, object] = Field(default_factory=dict)
    dynamic_state: CharacterDynamicState | None = None


__all__ = ["CharacterWorkingMemoryState"]
