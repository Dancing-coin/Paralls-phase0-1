from __future__ import annotations

from pydantic import Field

from app.character_agent.models.need_tension import RuntimeScalar, StrictRuntimeModel


class DriftCandidateRecord(StrictRuntimeModel):
    actor_id: str
    key: str
    direction: str
    reinforcing_events: int = Field(ge=0)
    cross_scene_count: int = Field(ge=0)
    stable_time_span: str
    confidence: RuntimeScalar = Field(ge=0.0, le=1.0)
    evidence_summary: str


__all__ = ["DriftCandidateRecord"]
