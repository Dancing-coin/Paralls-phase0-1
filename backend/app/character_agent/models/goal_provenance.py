"""Versioned provenance for action-free goal events; not an authority receipt."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GoalProposalProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    contract: Literal["goal_proposal:v1"]
    request_id: str = Field(min_length=1)
    turn_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    goal_revision: int = Field(ge=0)
    frame_digest: str = Field(min_length=1)
    evidence_refs: list[str]

    @model_validator(mode="after")
    def validate_identity(self) -> GoalProposalProvenance:
        if any(not value.strip() for value in (self.request_id, self.turn_id, self.source_ref, self.frame_digest)):
            raise ValueError("goal proposal provenance identity must not be blank")
        if self.source_ref not in self.evidence_refs or any(not ref.strip() for ref in self.evidence_refs):
            raise ValueError("goal proposal provenance requires trigger evidence")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("goal proposal provenance evidence must be unique")
        return self
