from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShortTermCoordinationContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    goal: str = Field(min_length=1)
    participants: tuple[str, ...]
    responsibilities: tuple[tuple[str, str], ...]
    expires_at: int = Field(ge=0)
    failure_conditions: tuple[str, ...]
    exit_conditions: tuple[str, ...]
    context_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_participants(self):
        if not self.participants or len(set(self.participants)) != len(self.participants):
            raise ValueError("coordination participants must be distinct")
        if any(actor not in self.participants for actor, _ in self.responsibilities):
            raise ValueError("responsibility must belong to a participant")
        return self


class LocalCoordinationSignal(BaseModel):
    """Sender observation attached to an existing percept; never a fact claim."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: str = Field(min_length=1)
    source: str = Field(min_length=1)
    observation: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]
    target: str = Field(min_length=1)
    expires_at: int = Field(ge=0)
    contract: ShortTermCoordinationContract | None = None

    def admits(self, *, actor_id: str, source_actor_id: str, now_ts: int,
               context_revision: str = "", participant_state: str = "proposed") -> bool:
        if self.target != actor_id or self.source != source_actor_id or now_ts >= self.expires_at:
            return False
        contract = self.contract
        return contract is None or (
            actor_id in contract.participants and self.source in contract.participants
            and now_ts < contract.expires_at and context_revision == contract.context_revision
            and participant_state in {"proposed", "accepted"}
        )
