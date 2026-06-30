from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CharacterBackgroundMode = Literal["off", "passive", "active", "quiet"]
CharacterSupervisionLevel = Literal["weak", "medium", "strong"]
CharacterSupervisionSource = Literal["siming_weak_default", "strategy_authorized", "gm_override"]


class CharacterUnresolvedTension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tension_id: str
    category: str
    summary: str
    target_ref: str = ""
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    status: Literal["active", "suppressed", "resolved"] = "active"
    source_event_id: str = ""
    source_stage: str = ""
    last_reinforced_ts: int = 0


class CharacterSupervisionConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_background_loop: bool = True
    background_mode: CharacterBackgroundMode = "passive"
    min_tick_interval_ms: int = Field(default=4000, ge=0)
    max_tick_budget_tokens: int = Field(default=600, ge=0)
    max_consecutive_ticks: int = Field(default=1, ge=0)
    wake_up_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    attention_theme: list[str] = Field(default_factory=list)
    preferred_watch_targets: list[str] = Field(default_factory=list)
    suppressed_watch_targets: list[str] = Field(default_factory=list)
    pressure_theme: str = ""
    caution_bias: Literal["low", "medium", "high"] = "low"
    blocked_goal_classes: list[str] = Field(default_factory=list)
    preferred_goal_classes: list[str] = Field(default_factory=list)
    protected_goal_classes: list[str] = Field(default_factory=list)
    goal_escalation_cap: Literal["none", "low", "medium"] = "none"
    allow_new_long_horizon_goals: bool = True
    blocked_intent_classes: list[str] = Field(default_factory=list)
    preferred_intent_classes: list[str] = Field(default_factory=list)
    force_conservative_intent_space: bool = False
    allow_proactive_initiation: bool = True
    allow_outcome_reflection: bool = True
    allow_goal_reappraisal: bool = True
    allow_relationship_reappraisal: bool = True
    allow_unresolved_tension_reactivation: bool = True
    allow_proactive_tendency_generation: bool = True
    constraint_summary: str = ""
    constraint_tags: list[str] = Field(default_factory=list)
    supervision_reason_code: str = ""
    supervision_reason_summary: str = ""


class CharacterSupervisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    actor_id: str
    requested_level: Literal["medium", "strong"]
    reason_code: str
    reason_summary: str
    requested_constraints: CharacterSupervisionConstraints
    requested_duration_ms: int = Field(default=0, ge=0)
    producer_ts: int = 0
    causation_id: str = ""
    correlation_id: str = ""


class CharacterSupervisionAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_id: str
    actor_id: str
    approved_level: CharacterSupervisionLevel
    approved_by: Literal["strategy_service", "gm_override"]
    approval_reason: str
    constraints: CharacterSupervisionConstraints
    effective_from_ts: int
    expires_at_ts: int = 0
    revocable: bool = True
    producer_ts: int = 0


class CharacterSupervisionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    current_level: CharacterSupervisionLevel = "weak"
    source: CharacterSupervisionSource = "siming_weak_default"
    active_constraints: CharacterSupervisionConstraints = Field(default_factory=CharacterSupervisionConstraints)
    entered_at_ts: int = 0
    expires_at_ts: int = 0
    last_refresh_ts: int = 0
    last_reason_summary: str = ""


class CharacterBackgroundCognitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    ran: bool
    producer_ts: int
    reason: str = ""
    interpretation_summary: str = ""
    selected_intent: str = ""
    current_level: CharacterSupervisionLevel = "weak"

