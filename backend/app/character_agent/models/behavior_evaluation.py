from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BehaviorEvaluation(BaseModel):
    """Evidence-backed evaluation of one actor turn.

    ``behavior_score`` remains a compatibility summary for older consumers. It
    is intentionally not the admission gate for ``candidate_policy``.
    """

    model_config = ConfigDict(extra="allow")

    actor_id: str
    turn_id: str = ""
    behavior_score: float = Field(ge=0.0, le=1.0)
    outcome_band: str = ""
    failure_domains: list[str] = Field(default_factory=list)
    comprehension_score: float | None = Field(default=None, ge=0.0, le=1.0)
    goal_progress_score: float | None = Field(default=None, ge=0.0, le=1.0)
    role_consistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    execution_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    social_consequence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    recovery_quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_refs: list[str] = Field(default_factory=list)
    unknown_dimensions: list[str] = Field(default_factory=list)
    unknown_reasons: dict[str, str] = Field(default_factory=dict)
    candidate_policy: dict[str, Any] | None = None

    # Compatibility fields retained from the original evaluator payload.
    context_hash: str = ""
    selected_memory_refs: list[str] = Field(default_factory=list)
    memory_budget: dict[str, Any] = Field(default_factory=dict)
    interpretation: dict[str, Any] = Field(default_factory=dict)
    selected_intent: str = ""
    failed_intent: str = ""
    execution_event_id: str = ""
    settlement_event_id: str = ""
    source_refs: list[str] = Field(default_factory=list)

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


__all__ = ["BehaviorEvaluation"]
