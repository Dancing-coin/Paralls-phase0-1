from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CharacterGoalHint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    source: str
    strength: float = Field(ge=0.0, le=1.0)
    evidence_tags: list[str] = Field(default_factory=list)


class CharacterGoalPortfolioEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: str
    goal: str
    horizon: Literal["long", "mid", "short"]
    status: Literal["active", "suspended", "blocked", "satisfied", "abandoned"] = "active"
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    urgency: Literal["low", "medium", "high"] = "low"
    source: str
    target_ref: str = ""
    blockers: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)


class CharacterActiveGoalFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_goal: str
    long_term_goal: str = ""
    mid_term_strategy: str = ""
    immediate_goal: str = ""
    supporting_goals: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    goal_sources: list[str] = Field(default_factory=list)
    urgency: Literal["low", "medium", "high"] = "low"
    dominant_goal_id: str = ""
    preserved_goal_ids: list[str] = Field(default_factory=list)
    suppressed_goal_ids: list[str] = Field(default_factory=list)
    goal_arbitration_summary: str = ""
    goal_portfolio: list[CharacterGoalPortfolioEntry] = Field(default_factory=list)


class CharacterGoalStateRecord(CharacterActiveGoalFrame):
    actor_id: str
    transition_kind: str = "initial"
    transition_reason_tags: list[str] = Field(default_factory=list)
