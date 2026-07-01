from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.models.cognition_delta import (
    CharacterBeliefDelta,
    CharacterDynamicStateDelta,
    CharacterHigherOrderDelta,
    CharacterSocialDelta,
)
from app.character_agent.models.goal_runtime import CharacterGoalHint


class CharacterCognitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpreted_situation: str
    belief_deltas: list[CharacterBeliefDelta] = Field(default_factory=list)
    social_deltas: list[CharacterSocialDelta] = Field(default_factory=list)
    higher_order_deltas: list[CharacterHigherOrderDelta] = Field(default_factory=list)
    dynamic_state_delta: CharacterDynamicStateDelta = Field(default_factory=CharacterDynamicStateDelta)
    goal_hints: list[CharacterGoalHint] = Field(default_factory=list)
    reasoning_trace_summary: str | None = None


__all__ = ["CharacterCognitionUpdate"]
